"""The reasoner, backed by the repository's OpenRouter client.

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

__all__ = ["AGENT_PARAMETERS", "LlmContentReasoner"]

logger = get_logger(__name__)

AGENT_PARAMETERS: Mapping[str, Any] = {
    # A decision, a short angle and a list of labels. A long answer is a sign
    # the model is writing the post instead of choosing what to write about.
    # Zero temperature because the same context should not produce two
    # different decisions, and ``PLAN.md`` Step 10 requires the decision to be
    # reproducible under a fake LLM and traceable to a prompt version under a
    # real one.
    "max_tokens": 500,
    "temperature": 0.0,
}


def _make_llm(model_id: str, parameters: Mapping[str, Any]):
    """The real client, built on demand — the same boundary as
    :func:`app.verification.judge._make_llm`.

    Imported here rather than at module scope so that importing the agent costs
    nothing and needs no credential: every test in the suite runs without one.
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
        return "".join(
            part if isinstance(part, str)
            else str(part.get("text", "")) if isinstance(part, dict)
            else str(part)
            for part in content
        )
    return str(content)


class LlmContentReasoner:
    """The Agent's reasoner, backed by the repository's OpenRouter client.

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
        self._model_id = model_id or config.MODEL_ID
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
