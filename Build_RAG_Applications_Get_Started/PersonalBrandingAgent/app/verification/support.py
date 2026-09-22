"""The advisory half of the gate: an interface, and the rule for its answers.

``PLAN.md`` Step 9 splits verification in two. The deterministic checks are
*authoritative*; the semantic ones — *claim semantically supported, claim
strength exceeds evidence strength, paraphrase changed meaning, wording
exaggerates experience* — are *advisory*, and they run only after the
deterministic checks pass. This module is the boundary between the two, and it
is deliberately thin: a request, an answer, and a protocol that anything can
implement.

Three decisions are made here rather than at the call site.

**The judge answers about claims by index.** Not by quoting a sentence — a
model that quotes can quote wrong, and a quote cannot be matched back to a
claim without trusting the quote. The request numbers the claims; the answer
names numbers. :func:`map_verdicts` then refuses any answer that names a claim
which was not asked about, because an advisory layer that can point at
nonexistent subjects is an advisory layer whose objections can be lost.

**A judge objection is reported, never hidden, and never rejecting.** The
deterministic checks are the gates; a model's reading of a sentence is a
finding a person should see. It routes to revision, which is the outcome for
findings about wording — see :data:`app.verification.policy.VIOLATION_SEVERITY`.

**Being unavailable is not the same as failing.** ``PLAN.md`` says the
deterministic gates still run when LLM assistance is unavailable, and that the
degraded mode is recorded. :class:`~app.verification.errors.SupportJudgeUnavailable`
says exactly that; the verifier turns it into ``degraded=True``. Any *other*
exception is a defect and fails closed — see
:func:`map_verdicts` and :mod:`app.verification.errors` for why the two are
not the same thing.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.verification.errors import VerificationError
from app.verification.enums import VerificationFailureCategory
from app.verification.models import SuppliedEvidence

__all__ = [
    "JudgeVerdict",
    "JudgedClaim",
    "JudgementRequest",
    "SupportJudge",
    "map_verdicts",
]


@dataclass(frozen=True)
class JudgedClaim:
    """One claim, with the evidence it is to be judged against.

    The evidence travels as :class:`~app.verification.models.SuppliedEvidence`
    — reference plus text — because a judge cannot judge a claim against a
    pointer. It is the *supplied* text and nothing else: the request is built
    from the context this verification was given, so a judge has no corpus to
    reach into and nothing to add to the evidence list.
    """

    index: int
    text: str
    evidence: tuple[SuppliedEvidence, ...] = ()


@dataclass(frozen=True)
class JudgementRequest:
    """Every claim the judge is asked about, in claim order.

    Claims that the deterministic checks already failed are absent: ``PLAN.md``
    runs the advisory checks *after* the deterministic ones, and asking a model
    about a sentence an exact string check has already rejected spends a call
    to learn nothing.
    """

    claims: tuple[JudgedClaim, ...] = ()
    prompt_version: str = ""


@dataclass(frozen=True)
class JudgeVerdict:
    """One answer: whether a claim is supported, and why not.

    ``reason`` is prose for a person reading a revision note. Nothing parses
    it, nothing branches on it, and it is never used to construct evidence —
    which is what keeps a model's explanation from becoming a source.
    """

    claim_index: int
    supported: bool
    reason: str = ""


@runtime_checkable
class SupportJudge(Protocol):
    """Anything that can be asked whether a claim is supported.

    Structural, not inherited: ``PLAN.md`` asks for the boundary to be
    injectable, and the test suite injects a plain object. The two attributes
    are recorded on the result so a report says which judge and which prompt
    produced the advisory half.
    """

    name: str
    prompt_version: str

    def judge(self, request: JudgementRequest) -> tuple[JudgeVerdict, ...]:
        """Judge every claim in ``request``.

        Raises:
            SupportJudgeUnavailable: the judge could not be consulted. The
                verifier records the degraded mode and lets the deterministic
                gates stand.
        """
        ...


def map_verdicts(request: JudgementRequest,
                 verdicts: tuple[JudgeVerdict, ...]) -> dict[int, JudgeVerdict]:
    """The verdicts keyed by claim index, refusing anything unasked-for.

    Two ways an answer can be unusable, and both fail closed rather than being
    ignored: a verdict about a claim that was not in the request, and two
    verdicts about the same claim. The first is the "do not trust unsupported
    identifiers" rule — the alternative is to silently drop the objection of a
    model that numbered its answer wrong, which is how an objection disappears.
    The second is the same problem in the other direction: with two answers for
    one claim there is no rule for which wins, and inventing one would be
    inventing policy.

    Raises:
        VerificationError: category ``JUDGE_FAILURE``. Not
            :class:`~app.verification.errors.SupportJudgeUnavailable`: the
            judge *did* answer, and its answer is unusable, which is a defect
            rather than an absence.
    """
    asked = {claim.index for claim in request.claims}
    mapped: dict[int, JudgeVerdict] = {}
    for verdict in verdicts:
        if verdict.claim_index not in asked:
            raise VerificationError(
                f"the support judge answered about claim "
                f"{verdict.claim_index}, which was not among the "
                f"{len(asked)} claim(s) it was asked about",
                category=VerificationFailureCategory.JUDGE_FAILURE,
            )
        if verdict.claim_index in mapped:
            raise VerificationError(
                f"the support judge answered twice about claim "
                f"{verdict.claim_index}",
                category=VerificationFailureCategory.JUDGE_FAILURE,
            )
        mapped[verdict.claim_index] = verdict
    return mapped
