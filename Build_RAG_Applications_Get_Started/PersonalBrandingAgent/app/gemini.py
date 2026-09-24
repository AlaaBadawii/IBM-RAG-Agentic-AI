"""Google Gemini client boundary: one pinned model, enforced JSON output.

Every model call the branding pipeline makes — Agent reasoning, draft
generation, support judging — goes through :class:`GeminiJsonClient`, which
presents the same ``invoke(messages) -> response`` seam the OpenAI-compatible
client used to, so no caller changes shape. Two deliberate differences from
the old boundary:

* The model is pinned (``config.GEMINI_MODEL_ID``), not routed. There is no
  router to serve a different model per call, which is what made token
  budgets unsizable and reproducibility unachievable under ``openrouter/free``
  (docs/implementation-status.md §18).
* The answer shape is enforced by the API (``response_mime_type`` +
  ``response_schema``), not extracted from free text afterwards. The
  ``parse_*`` functions downstream stay exactly where they are — a schema
  still describes what is *allowed*, and the strict parser is what *checks*
  it — but "the model did not answer with JSON" should now be unreachable
  short of a transport-level failure, rather than the modal failure.

What is intentionally *not* sent: ``temperature`` (and ``top_p``/``top_k``).
Google's API conventions for the pinned model family deprecate them in favour
of thinking effort, and setting them is a validation error on some paths —
whereas omitting them cannot fail the call. Determinism for an unattended
decision therefore rests on the pinned model plus the enforced schema, not on
a sampling parameter; ``PLAN.md`` Step 10's reproducibility requirement still
holds under a fake LLM exactly as before.

Importing this module costs nothing and needs no credential: the SDK import
is local and the key is read only inside :meth:`GeminiJsonClient.invoke`,
which is the only moment a real call is made.
"""

from typing import Any, Mapping
import time

from app import config
from app.logging_config import get_logger

__all__ = ["GeminiJsonClient", "GeminiJsonResponse"]

logger = get_logger(__name__)

#: How many times one logical call may hit the model. The first attempt plus
#: up to two retries — bounded, so an unattended run can never back off
#: forever inside a workflow that must finish or fail audibly.
MAX_ATTEMPTS = 3

#: Sleeps before attempts 2 and 3. Short exponential backoff: capacity sheds
#: are "usually temporary" per the provider, and two spaced retries cover a
#: minutes-long wobble without turning a scheduled run into a long poll.
RETRY_BACKOFF_SECONDS = (5.0, 15.0)

#: OpenAI-style roles the pipeline's prompts use, mapped onto Gemini roles.
_ROLE_MAP = {"user": "user", "assistant": "model", "model": "model"}


class GeminiJsonResponse:
    """The text of one model answer, behind the ``.content`` attribute the
    pipeline's ``_response_text`` helpers already read."""

    def __init__(self, content: str) -> None:
        self.content = content


class GeminiJsonClient:
    """One pinned Gemini model, answering JSON against a fixed schema.

    Args:
        model_id: the exact model to call (``config.GEMINI_MODEL_ID`` at the
            call sites, injectable for tests that never invoke).
        max_output_tokens: the call's output budget. Covers reasoning effort
            plus the emitted JSON on thinking models, which is why the
            ceilings sized under the old provider are kept as-is.
        response_schema: the answer shape as a plain-dict schema (``type``,
            ``properties``, ``items``, ``required``), converted to the SDK's
            ``types.Schema`` at call time so owning modules never import the
            SDK to state their shape.
    """

    def __init__(self, *, model_id: str, max_output_tokens: int,
                 response_schema: Mapping[str, Any]) -> None:
        self._model_id = model_id
        self._max_output_tokens = max_output_tokens
        self._response_schema = dict(response_schema)

    @property
    def model_id(self) -> str:
        """The exact model this client calls."""
        return self._model_id

    @property
    def response_schema(self) -> dict[str, Any]:
        """The answer shape this client enforces, as given."""
        return dict(self._response_schema)

    def invoke(self, messages: Any) -> GeminiJsonResponse:
        """Call the model once and return its JSON text.

        ``messages`` are the pipeline's ``(role, content)`` dicts or tuples;
        ``system`` becomes the system instruction, everything else becomes
        content in order. A 503 (capacity shed) is retried with backoff, up
        to :data:`MAX_ATTEMPTS` total attempts; anything else — bad auth,
        invalid schema, any 4xx — is raised immediately, because those are
        real errors a retry cannot fix. Raises whatever the transport raises
        on the final attempt — callers classify failures themselves — and
        :class:`app.errors.ConfigError` when no key is configured.
        """
        from google import genai
        from google.genai import types

        key = config.require_google_key()
        system, contents = _split_messages(messages)
        client = genai.Client(api_key=key)
        request_config = types.GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            response_schema=_to_schema(self._response_schema),
            max_output_tokens=self._max_output_tokens,
        )
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = client.models.generate_content(
                    model=self._model_id,
                    contents=contents,
                    config=request_config,
                )
            except Exception as exc:
                last_error = exc
                if _is_capacity_shed(exc) and attempt < MAX_ATTEMPTS:
                    delay = RETRY_BACKOFF_SECONDS[attempt - 1]
                    logger.warning(
                        "gemini call (model=%s) shed by the provider "
                        "(attempt %d/%d); retrying in %.0fs",
                        self._model_id, attempt, MAX_ATTEMPTS, delay,
                    )
                    time.sleep(delay)
                    continue
                raise
            logger.info(
                "gemini call (model=%s) answered on attempt %d/%d",
                self._model_id, attempt, MAX_ATTEMPTS,
            )
            return GeminiJsonResponse(response.text or "")
        assert last_error is not None  # the loop always raises or returns
        raise last_error


def _is_capacity_shed(exc: Exception) -> bool:
    """True only for a provider 503: shed load, worth one more chance.

    Auth failures, unknown models, rejected schemas — every 4xx — return
    False: retrying those is how a misconfiguration becomes a slow
    misconfiguration.
    """
    from google.genai import errors

    return isinstance(exc, errors.ServerError) and exc.code == 503


def _split_messages(messages: Any) -> tuple[str, list]:
    """Split prompt messages into a system instruction and Gemini contents."""
    from google.genai import types

    system_parts: list[str] = []
    contents: list = []
    for message in messages:
        if isinstance(message, Mapping):
            role, content = message.get("role"), message.get("content")
        else:
            role, content = message[0], message[1]
        text = content if isinstance(content, str) else str(content or "")
        if role == "system":
            system_parts.append(text)
            continue
        try:
            gemini_role = _ROLE_MAP[role]
        except KeyError:
            raise ValueError(
                f"unsupported message role for Gemini: {role!r}"
            ) from None
        contents.append(
            types.Content(
                role=gemini_role, parts=[types.Part.from_text(text=text)]
            )
        )
    return "\n\n".join(system_parts), contents


def _to_schema(node: Mapping[str, Any]) -> Any:
    """Convert a plain-dict schema into the SDK's ``types.Schema``."""
    from google.genai import types

    type_map = {
        "object": types.Type.OBJECT,
        "array": types.Type.ARRAY,
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
    }
    kwargs: dict[str, Any] = {"type": type_map[node["type"]]}
    if "description" in node:
        kwargs["description"] = node["description"]
    if "properties" in node:
        kwargs["properties"] = {
            name: _to_schema(sub) for name, sub in node["properties"].items()
        }
    if "items" in node:
        kwargs["items"] = _to_schema(node["items"])
    if "required" in node:
        kwargs["required"] = list(node["required"])
    return types.Schema(**kwargs)
