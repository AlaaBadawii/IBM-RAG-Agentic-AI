"""The reasoner, backed by the pinned Gemini model with enforced JSON output.

The mirror of :class:`app.verification.judge.LlmSupportJudge`, with one
difference that follows from where each sits.

The judge is *advisory*: when it cannot be consulted, ``PLAN.md`` Step 9 keeps
the deterministic gates running and records the degraded mode, so
:class:`~app.verification.errors.SupportJudgeUnavailable` is a domain signal the
verifier can absorb. The reasoner is not advisory — it is the only thing that
decides what to write about, and there is no deterministic half of that
decision to fall back on. So
:class:`~app.agent.errors.ReasoningUnavailable` is a *failure*, and the Agent
turns it into ``DO_NOT_PUBLISH``. ``PLAN.md`` Step 10, Failure/recovery:
*"Never a fallback that publishes something weaker."*

Everything else propagates. A bug in this class is not an unavailable
reasoner, and reporting it as one would be the Agent failing open on the
strength of its own defect — the same rule the judge states about itself.
"""
from typing import Any, Mapping

from app import config
from app.agent.errors import ReasoningUnavailable
from app.agent.models import ReasoningAnswer, ReasoningRequest
from app.agent.prompt import (
    AGENT_PROMPT_VERSION,
    build_reasoning_prompt,
    parse_reasoning_answer,
)
from app.logging_config import get_logger, redact

__all__ = ["AGENT_PARAMETERS", "REASONING_RESPONSE_SCHEMA", "LlmContentReasoner"]

logger = get_logger(__name__)

AGENT_PARAMETERS: Mapping[str, Any] = {
    # A decision, a short angle and a list of labels. A long answer is a sign
    # the model is writing the post instead of choosing what to write about.
    #
    # ``max_tokens`` is translated to the Gemini ``max_output_tokens`` budget
    # at the client boundary (:mod:`app.gemini`). The budget covers the
    # emitted JSON; 3000 is kept from the OpenRouter era, where the same
    # number had to cover hidden reasoning *plus* the answer (at 500 the
    # routed model truncated mid-object and every run ended
    # ``REASONING_FAILED``). If the pinned model ever truncates, raise this —
    # a truncation still presents as ``finish_reason: "length"`` and "did
    # not answer with JSON", never as a short answer.
    #
    # No temperature: the pinned model family does not accept sampling
    # parameters (Google's API conventions deprecate them in favour of
    # thinking effort, and setting them is a validation error on some
    # paths). Determinism rests on the pinned model plus the enforced
    # response schema below; ``PLAN.md`` Step 10's reproducibility
    # requirement still holds under a fake LLM exactly as before.
    "max_tokens": 3000,
}

#: The answer shape the reasoner must produce, enforced by the API rather
#: than extracted from free text afterwards. Every field the strict parser
#: (:func:`~app.agent.prompt.parse_reasoning_answer`) reads is required
#: here, so "the model did not answer with JSON" is unreachable short of a
#: transport-level failure instead of the modal failure as it was under the
#: routed provider.
REASONING_RESPONSE_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "publish": {"type": "boolean"},
        "topic": {"type": "string"},
        "angle": {"type": "string"},
        "project": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
        },
        "strategy": {"type": "string"},
        "rationale": {"type": "string"},
        "decline_reason": {"type": "string"},
    },
    "required": [
        "publish", "topic", "angle", "project", "evidence", "strategy",
        "rationale", "decline_reason",
    ],
}


def _make_llm(model_id: str, parameters: Mapping[str, Any]):
    """The real client: the pinned Gemini model with enforced JSON output.

    Imported here rather than at module scope so that importing the agent costs
    nothing and needs no credential: every test in the suite runs without one.
    The key is still validated eagerly (no network involved), so a missing key
    is a configuration error at build time, not a mystery at call time.
    """
    from app.gemini import GeminiJsonClient

    params = dict(parameters)
    config.require_google_key()
    return GeminiJsonClient(
        model_id=model_id,
        max_output_tokens=params["max_tokens"],
        response_schema=REASONING_RESPONSE_SCHEMA,
    )


def _response_text(response: Any) -> str:
    """The text of a chat response, whatever shape the client used."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        return "".join(
            part if isinstance(part, str)
            else str(part.get("text", "")) if isinstance(part, dict)
            else str(part)
            for part in content
        )
    return str(content)


class LlmContentReasoner:
    """The Agent's reasoner, backed by the pinned Gemini model.

    The class that decides what *unavailable* means. Everything that stops it
    from producing a usable answer — no credential, a client that will not
    build, a request that fails, a response nobody can parse — is raised as
    :class:`~app.agent.errors.ReasoningUnavailable`, and the Agent turns that
    into ``DO_NOT_PUBLISH`` with the failure exposed for the workflow to
    notify. Nothing here notifies anybody: ``PLAN.md`` Step 10 keeps that in
    the workflow.
    """

    name = "llm-content-reasoner"

    def __init__(self, llm=None, *, model_id: str | None = None,
                 parameters: Mapping[str, Any] | None = None,
                 prompt_version: str = AGENT_PROMPT_VERSION):
        """
        Args:
            llm: anything with ``invoke(messages) -> response``. Injected by
                tests; when absent the real client is built at call time, which
                is the only moment a credential is needed.
            model_id: passed to the client and recorded on the proposal, so a
                decision can be traced to the model that made it.
            parameters: reasoning parameters. Defaults to
                :data:`AGENT_PARAMETERS`, not the generation ones: this is a
                choice, not a piece of writing.
            prompt_version: recorded on the proposal alongside the model id.
        """
        self._llm = llm
        self._model_id = model_id or config.GEMINI_MODEL_ID
        self._parameters = dict(
            AGENT_PARAMETERS if parameters is None else parameters
        )
        self.prompt_version = prompt_version

    @property
    def model_id(self) -> str:
        """The model id recorded on every proposal this reasoner produces."""
        return self._model_id

    def reason(self, request: ReasoningRequest) -> ReasoningAnswer:
        """Ask the model what is worth publishing, from what.

        Raises:
            ReasoningUnavailable: see the class docstring. Never raises
                anything else for a model or transport problem.
        """
        prompt = build_reasoning_prompt(request, version=self.prompt_version)
        messages = [dict(message) for message in prompt.messages()]

        try:
            llm = self._llm if self._llm is not None else _make_llm(
                self._model_id, self._parameters
            )
        except config.ConfigError as exc:
            raise ReasoningUnavailable(redact(str(exc))) from exc
        except Exception as exc:  # noqa: BLE001 - the client's own build errors
            raise ReasoningUnavailable(
                f"the branding agent's client could not be built: "
                f"{type(exc).__name__}"
            ) from exc

        try:
            response = llm.invoke(messages)
        except config.ConfigError as exc:
            raise ReasoningUnavailable(redact(str(exc))) from exc
        except Exception as exc:  # noqa: BLE001 - transport, auth, rate limit…
            raise ReasoningUnavailable(
                f"the branding agent could not be reached: "
                f"{type(exc).__name__}"
            ) from exc

        answer = parse_reasoning_answer(_response_text(response))
        logger.info(
            "branding agent answered %s about %s (%d evidence label(s), "
            "model=%s, prompt=%s)",
            "publish" if answer.publish else "do not publish",
            answer.topic or "nothing",
            len(answer.evidence_labels),
            self._model_id, self.prompt_version,
        )
        return answer
