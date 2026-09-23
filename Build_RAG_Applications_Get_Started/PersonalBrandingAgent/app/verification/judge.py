"""The judge that is actually a model: one question, one call, one shape.

``PLAN.md`` Step 9 lists four advisory checks — *claim semantically supported,
claim strength exceeds evidence strength, paraphrase changed meaning, wording
exaggerates experience*. They are four ways of asking one thing, and this asks
it once per claim: **does the evidence you were shown state this?** A model
that answers that is useful precisely where the deterministic layer is blind —
paraphrase, an overstatement, a sentence that reads as more than its source
says — and it is useless everywhere else, so it is given nothing else to do.

What it is given matters more than what it is asked. The judge sees the claim
and the supplied evidence text, and **only** supplied evidence text: no corpus,
no retrieval, no store. It is asked for claim *numbers*, not quotations,
because a number either names a claim that was sent or does not — and a quote
cannot be checked without trusting the quote. Its answer is parsed strictly and
an unparseable one is :class:`~app.verification.errors.SupportJudgeUnavailable`,
never a silent pass.

Nothing here reads the clock, the environment or a random source, and no
message this module builds can contain a secret: the only inputs are the
claim and the evidence text.
"""
import json
import re
from typing import Any, Mapping

from app import config
from app.errors import ConfigError
from app.generation.prompt import PROHIBITED_CLAIMS
from app.logging_config import get_logger, redact
from app.verification.errors import SupportJudgeUnavailable
from app.verification.support import JudgeVerdict, JudgementRequest

__all__ = [
    "JUDGE_PROMPT_VERSION",
    "SUPPORT_JUDGE_PARAMETERS",
    "LlmSupportJudge",
    "build_judgement_messages",
    "parse_judgement",
]

logger = get_logger(__name__)


def _prohibited_phrase(claims: tuple[str, ...] = PROHIBITED_CLAIMS) -> str:
    """``a, b, or c`` — the same construction
    :func:`app.generation.prompt._prohibited_phrase` uses, stated here so this
    module's prompt is built from the corpus's list without importing a
    private helper out of another layer."""
    if not claims:
        return ""
    if len(claims) == 1:
        return claims[0]
    return ", ".join(claims[:-1]) + " or " + claims[-1]


_PROHIBITED_PHRASE = _prohibited_phrase()

#: Bumped whenever the wording below changes in a way that could change an
#: answer. Recorded on every result that consulted a judge, so an advisory
#: finding can be traced to the prompt that produced it.
JUDGE_PROMPT_VERSION = "support-judge-v1"

SUPPORT_JUDGE_PARAMETERS: Mapping[str, Any] = {
    # A judge is asked for a boolean and a sentence per claim; a long answer
    # is a sign it is doing something else.
    #
    # Same arithmetic as ``app.agent.llm.AGENT_PARAMETERS``: the cap covers the
    # model's hidden reasoning as well as the JSON it finally emits. At 600 the
    # judge was truncated on every run, which surfaced only as
    # ``degraded: True`` with "the support judge did not answer with JSON" —
    # because the advisory layer is *allowed* to degrade, that failure was
    # silent by design while the deterministic gates still owned the outcome.
    #
    # 4000, not the Agent's 3000: measured against the live provider, 3000 was
    # still truncated. The router served ``nvidia/nemotron-3.5-lightning:free``
    # for that call, which spent 3452 reasoning tokens against the 3000 cap and
    # emitted no JSON at all (``finish_reason: "length"``). At 4000 the same
    # request parsed on 7 of 8 consecutive calls.
    #
    # That 7-of-8 is the honest number, and it is why this value is a
    # mitigation rather than a fix. The eighth call did **not** truncate — it
    # answered within budget and the answer contained no verdicts, because the
    # router had served ``liquid/lfm-2.5-2.6b:free``, a model too small to
    # follow the schema. Eight consecutive calls were served by eight
    # *different* models. No fixed cap bounds a requirement that moves with an
    # unknown model, and no cap fixes a model that cannot follow the
    # instruction; both need the model pinned. Until then a degraded judgement
    # is possible on any run, and the deterministic gates remain the only ones
    # allowed to decide the outcome.
    #
    # Zero temperature because the same draft and the same evidence should not
    # produce two different gates.
    "max_tokens": 4000,
    "temperature": 0.0,
}

_JUDGE_SYSTEM = (
    "You are an evidence verifier. You are given numbered claims from a draft "
    "and, for each claim, the text of the only evidence the draft is allowed "
    "to rest on.\n"
    "\n"
    "For each claim, decide whether that evidence states the claim. Judge "
    "strictly:\n"
    "- A claim is supported only if the evidence says it. Plausible, likely, "
    "typical and consistent-with are not supported.\n"
    "- Evidence of studying, planning or wanting something never supports a "
    "claim that it was done.\n"
    "- Never accept a claim about " + _PROHIBITED_PHRASE + " that the evidence "
    "does not state.\n"
    "- Paraphrase that keeps the meaning is fine. Wording that claims more "
    "than the evidence says is not.\n"
    "- Do not use knowledge from outside the evidence shown to you. If the "
    "evidence is silent, the claim is not supported.\n"
    "\n"
    "Answer only with JSON, in exactly this shape:\n"
    '{"verdicts": [{"claim_index": 1, "supported": true, "reason": ""}]}\n'
    "One entry per claim, using the claim's own number, with a short reason "
    "when supported is false. Do not invent claim numbers."
)


def build_judgement_messages(request: JudgementRequest) -> list[tuple[str, str]]:
    """The messages for one judgement, as ``(role, content)`` pairs.

    Deterministic: claim order is the request's order, evidence order is the
    order it was supplied in, and each claim is labelled with the number the
    answer must use. Empty evidence is printed as empty — a judge told nothing
    about a claim has to say it cannot tell, and the alternative (omitting the
    claim) would be an answer of silence.
    """
    parts: list[str] = []
    for claim in request.claims:
        parts.append(f"CLAIM {claim.index}\n{claim.text}\n")
        if not claim.evidence:
            parts.append("EVIDENCE FOR THIS CLAIM\n(none supplied)\n")
            continue
        parts.append("EVIDENCE FOR THIS CLAIM\n")
        for evidence in claim.evidence:
            reference = evidence.reference
            state = reference.evidence_state or "none declared"
            parts.append(
                f"[{reference.label or '-'}] source: {reference.source} "
                f"(chunk {reference.chunk_id}, evidence state: {state})\n"
                f"{evidence.content}\n"
            )
        parts.append("")
    return [
        ("system", _JUDGE_SYSTEM),
        ("user", "\n".join(parts).strip()),
    ]


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_judgement(text: str) -> tuple[JudgeVerdict, ...]:
    """The verdicts in a model's answer.

    Strict about the shape and forgiving about the wrapping, because asking a
    model for bare JSON reliably produces JSON in a code fence. Anything that
    is not a verdict is
    :class:`~app.verification.errors.SupportJudgeUnavailable`: an answer nobody
    can read is an answer, which makes this the degraded mode rather than a
    pass.

    Raises:
        SupportJudgeUnavailable: the answer is not the required shape — not
            JSON, no verdicts, a missing boolean, or a claim index that is not
            an integer. All of them mean *the advisory layer could not be
            consulted*, which the caller records; none of them mean the
            deterministic checks should stop running.
    """
    match = _JSON_BLOCK.search(text or "")
    if not match:
        raise SupportJudgeUnavailable(
            "the support judge did not answer with JSON"
        )
    try:
        payload = json.loads(match.group(0))
    except ValueError as exc:
        raise SupportJudgeUnavailable(
            f"the support judge's answer was not valid JSON: {type(exc).__name__}"
        ) from exc

    entries = payload.get("verdicts") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise SupportJudgeUnavailable(
            "the support judge's answer contained no verdicts"
        )

    verdicts: list[JudgeVerdict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SupportJudgeUnavailable(
                "the support judge's answer contained a verdict that is not "
                "an object"
            )
        index = entry.get("claim_index")
        supported = entry.get("supported")
        if not isinstance(index, int) or isinstance(index, bool):
            raise SupportJudgeUnavailable(
                "the support judge's answer named a claim with a non-integer "
                "index"
            )
        if not isinstance(supported, bool):
            raise SupportJudgeUnavailable(
                f"the support judge's verdict about claim {index} carried no "
                f"boolean"
            )
        reason = entry.get("reason")
        verdicts.append(JudgeVerdict(
            claim_index=index,
            supported=supported,
            reason=reason.strip() if isinstance(reason, str) else "",
        ))
    return tuple(verdicts)


def _make_llm(model_id: str, parameters: Mapping[str, Any]):
    """The real client, built on demand — the same boundary as
    :func:`app.generation.generator._make_llm`.

    Imported here rather than at module scope so that importing the
    verification layer costs nothing and needs no credential.
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


class LlmSupportJudge:
    """The advisory judge, backed by the repository's OpenRouter client.

    The class that decides what *unavailable* means. Everything that stops it
    from producing a usable answer — no credential, a client that will not
    build, a request that fails, a response nobody can parse — is raised as
    :class:`~app.verification.errors.SupportJudgeUnavailable`, because
    ``PLAN.md`` allows the run to continue on the deterministic gates alone
    when the advisory layer is missing.

    Everything *else* propagates. A bug in this class is not an unavailable
    judge, and reporting it as one would be the verifier failing open on the
    strength of its own defect.
    """

    name = "llm-support-judge"

    def __init__(self, llm=None, *, model_id: str | None = None,
                 parameters: Mapping[str, Any] | None = None,
                 prompt_version: str = JUDGE_PROMPT_VERSION):
        """
        Args:
            llm: anything with ``invoke(messages) -> response``. Injected by
                tests; when absent the real client is built at call time,
                which is the only moment a credential is needed.
            model_id: passed to the client and recorded on the result.
            parameters: judge parameters. Defaults to
                :data:`SUPPORT_JUDGE_PARAMETERS`, not the generation ones:
                this is a classification, not a piece of writing.
            prompt_version: recorded, so an advisory finding can be traced to
                the prompt that produced it.
        """
        self._llm = llm
        self._model_id = model_id or config.MODEL_ID
        self._parameters = dict(
            SUPPORT_JUDGE_PARAMETERS if parameters is None else parameters
        )
        self.prompt_version = prompt_version

    def judge(self, request: JudgementRequest) -> tuple[JudgeVerdict, ...]:
        """Ask the model about every claim in ``request``.

        Raises:
            SupportJudgeUnavailable: see the class docstring. Never raises
                anything else for a model or transport problem.
        """
        if not request.claims:
            return ()
        messages = [
            {"role": role, "content": content}
            for role, content in build_judgement_messages(request)
        ]
        try:
            llm = self._llm if self._llm is not None else _make_llm(
                self._model_id, self._parameters
            )
        except ConfigError as exc:
            raise SupportJudgeUnavailable(redact(str(exc))) from exc
        except Exception as exc:  # noqa: BLE001 - the client's own build errors
            raise SupportJudgeUnavailable(
                f"the support judge's client could not be built: "
                f"{type(exc).__name__}"
            ) from exc

        try:
            response = llm.invoke(messages)
        except ConfigError as exc:
            raise SupportJudgeUnavailable(redact(str(exc))) from exc
        except Exception as exc:  # noqa: BLE001 - transport, auth, rate limit…
            raise SupportJudgeUnavailable(
                f"the support judge could not be reached: {type(exc).__name__}"
            ) from exc

        verdicts = parse_judgement(_response_text(response))
        logger.info(
            "support judge answered about %d claim(s) (%d unsupported, "
            "model=%s, prompt=%s)",
            len(verdicts),
            sum(1 for verdict in verdicts if not verdict.supported),
            self._model_id, self.prompt_version,
        )
        return verdicts
