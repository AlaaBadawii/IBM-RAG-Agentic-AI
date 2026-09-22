"""The generation service: one context in, one candidate post out.

``PLAN.md`` Step 8 asks for a *bounded, testable transformation* rather than
the centre of the system, and this module is where that shape is enforced. The
sequence is fixed and short:

    request  ->  assemble the prompt  ->  no evidence? decline
              ->  call the model      ->  unparseable? fail
              ->  decline?            ->  a report
              ->  resolve citations   ->  a structured result

Four decisions worth stating, because each one is a place a generator usually
goes wrong:

**A decline is decided before the model is called.** If the assembled context
carries no evidence, there is nothing to ground a post in, and asking a model
anyway is asking it to invent. The check is deterministic, costs nothing, and
is the one place where "insufficient evidence" is answered by the system rather
than by the model.

**A failure raises; it never becomes a weaker post.** No placeholder, no
truncation, no "best effort" text. A failed generation is a failed phase, and
the workflow that catches it records ``WORKFLOW_FAILED`` and notifies. The only
exception to the exception is a missing credential, which is categorized
:attr:`~app.generation.enums.GenerationFailureCategory.CONFIGURATION` because
retrying cannot fix it — a person has to.

**Citations are resolved, never trusted.** The model answers with labels
(``E1``, ``E2``) drawn from the list the prompt sent. A label that resolves
becomes a citation; a label that does not is reported in
``GeneratedPost.unresolved_labels`` and becomes nothing else. So the draft can
only ever cite evidence that was supplied — not because the model was asked
nicely, but because there is no code path from an invented label to a citation.

**The model is injected, and only the real path touches configuration.** A
test drives this class with a plain object that has ``.invoke()``, which is why
the whole suite runs offline with no key and no network. The real client is
built lazily, at the moment of the call, following
``app/retrieval/multi_query.py``: the repository's existing OpenRouter client,
with the repository's existing generation parameters.
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from app import config
from app.errors import ConfigError
from app.generation.enums import (
    DeclineReason,
    GenerationFailureCategory,
    GenerationOutcome,
)
from app.generation.errors import GenerationError
from app.generation.models import (
    EvidenceCitation,
    GeneratedPost,
    GenerationMetadata,
    GenerationPrompt,
    GenerationRequest,
    GenerationResult,
)
from app.generation.prompt import PROMPT_VERSION, build_prompt
from app.logging_config import get_logger, redact

logger = get_logger(__name__)

__all__ = ["ModelOutput", "PostGenerator", "parse_generation_output"]


@dataclass(frozen=True)
class ModelOutput:
    """One model answer, after parsing and before any resolution.

    Deliberately not the public result: this is what the *model* said, which is
    unverified text plus unverified labels. :class:`PostGenerator` is what turns
    it into a :class:`~app.generation.models.GenerationResult` by resolving the
    labels against the evidence that was actually sent.
    """

    declined: bool
    post: str = ""
    evidence_labels: tuple[str, ...] = ()
    reason: str = ""


def _strip_code_fence(text: str) -> str:
    """Remove a ```json … ``` wrapper, if the model added one.

    Models wrap JSON in a fence often enough that treating it as a malformed
    answer would fail generations that are perfectly usable. Stripping is not
    leniency about the *content* — the payload still has to parse and still has
    to carry the required fields.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_generation_output(text: str) -> ModelOutput:
    """Parse the model's answer into :class:`ModelOutput`.

    Raises:
        GenerationError: the answer is not the required JSON object, or it
            claims a post and carries no text. Both are
            :attr:`~app.generation.enums.GenerationFailureCategory.INVALID_RESPONSE`
            — there is no post to check and nothing to publish, and extracting
            something post-shaped from prose would be fabrication by another
            route.
    """
    payload_text = _strip_code_fence(text or "")
    payload: Any = None
    try:
        payload = json.loads(payload_text)
    except (ValueError, TypeError):
        # A model that narrates before or after the object is still usable if
        # the object is intact; take the outermost braces and try once more.
        start, end = payload_text.find("{"), payload_text.rfind("}")
        if start != -1 and end > start:
            try:
                payload = json.loads(payload_text[start:end + 1])
            except (ValueError, TypeError):
                payload = None

    if not isinstance(payload, dict):
        raise GenerationError(
            "the model did not return the required JSON object",
            category=GenerationFailureCategory.INVALID_RESPONSE,
        )

    declined = bool(payload.get("declined", False))
    post = payload.get("post") or ""
    if not isinstance(post, str):
        raise GenerationError(
            f"the model's post field was {type(post).__name__}, not text",
            category=GenerationFailureCategory.INVALID_RESPONSE,
        )

    raw_labels = payload.get("evidence_used") or []
    if not isinstance(raw_labels, (list, tuple)):
        raw_labels = []
    labels = tuple(str(label).strip() for label in raw_labels if str(label).strip())

    reason = payload.get("reason") or ""
    reason = reason if isinstance(reason, str) else str(reason)

    if not declined and not post.strip():
        raise GenerationError(
            "the model returned neither a post nor a decline",
            category=GenerationFailureCategory.INVALID_RESPONSE,
        )

    return ModelOutput(
        declined=declined,
        post=post.strip(),
        evidence_labels=labels,
        reason=reason.strip(),
    )


def _make_llm(model_id: str, parameters: Mapping[str, Any]):
    """The real client: the repository's OpenRouter setup, built on demand.

    Imported here rather than at module scope so that importing the generation
    layer — which the test suite does constantly — costs nothing and needs no
    credential. This mirrors ``app/retrieval/multi_query.py``, which is the
    working OpenRouter pattern ``PLAN.md`` Step 8 points at.
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=config.require_openrouter_key(),
        base_url=config.OPENROUTER_BASE_URL,
        model=model_id,
        **dict(parameters),
    )


def _response_text(response: Any) -> str:
    """The text of a chat response, whatever shape the client used."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        # Some providers return content blocks; keep the text parts in order.
        return "".join(
            part if isinstance(part, str)
            else str(part.get("text", "")) if isinstance(part, dict)
            else str(part)
            for part in content
        )
    return str(content)


class PostGenerator:
    """Turns an assembled context into a candidate post, or a decline.

    Constructed once per workflow configuration, not per post: it holds no
    state between calls, so the same instance can be reused and two calls with
    the same request produce the same prompt.
    """

    def __init__(self, llm=None, *, model_id: str | None = None,
                 parameters: Mapping[str, Any] | None = None,
                 prompt_version: str = PROMPT_VERSION):
        """
        Args:
            llm: anything with ``invoke(messages) -> response`` where the
                response has ``content``. Injected by tests; when absent, the
                real OpenRouter client is built at call time, which is the only
                moment a credential is needed.
            model_id: recorded in the metadata and passed to the client.
            parameters: generation parameters, recorded verbatim. Defaults to
                the repository's configured ``GENERATION_PARAMS``.
            prompt_version: recorded in the metadata, so a post can be traced
                to the prompt that produced it.
        """
        self._llm = llm
        self._model_id = model_id or config.MODEL_ID
        self._parameters = dict(
            config.GENERATION_PARAMS if parameters is None else parameters
        )
        self._prompt_version = prompt_version

    # -- what a caller uses -------------------------------------------------

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Produce a candidate post, or decline to.

        Raises:
            GenerationError: the model could not be reached, is not configured,
                or did not answer in the required shape. Never for a decline —
                that is a result — and never for a draft this layer merely
                suspects is weak; Step 9 decides that.
        """
        prompt = build_prompt(request, version=self._prompt_version)
        if not prompt.has_evidence:
            return self._declined(
                request, prompt, DeclineReason.INSUFFICIENT_EVIDENCE,
                "the assembled context carries no evidence to ground a post in",
            )

        started = time.perf_counter()
        raw = self._invoke(prompt)
        output = parse_generation_output(raw)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        metadata = self._metadata(request, prompt, latency_ms=latency_ms)

        if output.declined:
            return GenerationResult(
                outcome=GenerationOutcome.DECLINED,
                metadata=metadata,
                decline_reason=DeclineReason.MODEL_DECLINED,
                decline_message=(
                    output.reason
                    or "the model reported that the supplied evidence does "
                       "not support a post"
                ),
            )

        post = self._resolve(output, prompt)
        logger.info(
            "generated a candidate post (%d chars, %d citation(s), %d "
            "unresolved label(s), model=%s, prompt=%s)",
            len(post.content), len(post.citations),
            len(post.unresolved_labels), self._model_id, self._prompt_version,
        )
        return GenerationResult(
            outcome=GenerationOutcome.GENERATED, metadata=metadata, post=post,
        )

    # -- internals ----------------------------------------------------------

    def _invoke(self, prompt: GenerationPrompt) -> str:
        """Call the model. The only place a request is made."""
        try:
            llm = self._llm if self._llm is not None else _make_llm(
                self._model_id, self._parameters
            )
        except ConfigError as exc:
            raise GenerationError(
                str(exc), category=GenerationFailureCategory.CONFIGURATION,
            ) from exc
        try:
            response = llm.invoke(prompt.messages())
        except Exception as exc:
            # The message is external input and is redacted before it is kept,
            # with the same list the log filter and the notifier use.
            raise GenerationError(
                f"the generation model could not be reached: {redact(str(exc))}",
                category=GenerationFailureCategory.LLM_UNAVAILABLE,
            ) from exc
        return _response_text(response)

    def _resolve(self, output: ModelOutput,
                 prompt: GenerationPrompt) -> GeneratedPost:
        """Attach the model's labels to the evidence that was actually sent.

        The resolution is a lookup in the prompt's own citation list, so a
        label the model invented has no citation to become. Unresolved labels
        are reported rather than dropped: a draft citing a source it was never
        given is something Step 9 has to be able to see, and a silently
        discarded label is exactly the evidence of that which disappears.
        """
        known = {citation.label: citation for citation in prompt.citations}
        citations: list[EvidenceCitation] = []
        unresolved: list[str] = []
        for label in output.evidence_labels:
            citation = known.get(label)
            if citation is None:
                unresolved.append(label)
                continue
            if citation not in citations:
                citations.append(citation)
        return GeneratedPost(
            content=output.post,
            citations=tuple(citations),
            unresolved_labels=tuple(unresolved),
        )

    def _metadata(self, request: GenerationRequest, prompt: GenerationPrompt,
                  *, latency_ms: float | None = None) -> GenerationMetadata:
        return GenerationMetadata(
            model_id=self._model_id,
            prompt_version=prompt.version,
            parameters=dict(self._parameters),
            evidence_item_count=len(prompt.citations),
            guidance_item_count=len(request.context.guidance_items()),
            evidence_labels=tuple(c.label for c in prompt.citations),
            latency_ms=latency_ms,
        )

    def _declined(self, request: GenerationRequest, prompt: GenerationPrompt,
                  reason: DeclineReason, message: str) -> GenerationResult:
        """A decline that never reached the model.

        ``latency_ms`` stays ``None``: no call was made, and a plausible-looking
        duration on a result that never left the machine would be a fabricated
        measurement in an audit record.
        """
        return GenerationResult(
            outcome=GenerationOutcome.DECLINED,
            metadata=self._metadata(request, prompt),
            decline_reason=reason,
            decline_message=message,
        )
