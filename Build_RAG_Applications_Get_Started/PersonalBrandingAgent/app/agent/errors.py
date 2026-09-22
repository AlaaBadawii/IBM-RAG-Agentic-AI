"""The three ways the agent's reasoning can fail (``PLAN.md`` Step 10).

Every one of them ends the run as ``DO_NOT_PUBLISH``. That is the whole
failure policy: ``PLAN.md`` Step 10, Failure/recovery — *"Agent reasoning
failure -> ``DO_NOT_PUBLISH`` plus a notification. **Never** a fallback that
publishes something weaker."* So none of these exceptions escapes the agent;
:class:`~app.agent.agent.BrandingAgent` catches them, turns each into a
``DO_NOT_PUBLISH`` result carrying an
:class:`~app.agent.models.AgentFailure`, and leaves the notification to the
workflow. The type exists so the *reason* survives that conversion — a
workflow that only saw "no post" could not tell a missing credential from a
model inventing a source.

The distinction between them is the distinction between the repairs:

:class:`ReasoningUnavailable`
    No answer at all. A missing key, an unreachable endpoint, a reply that is
    not the required JSON. The next scheduled run may simply succeed.

:class:`UnusableReasoningAnswer`
    An answer, and it cannot become a proposal: a topic that is not an
    opportunity this context holds, a retrieval strategy outside the allowed
    vocabulary, or a decision to publish with no evidence selected. The model
    answered *outside* what it was given, which is the failure mode the prompt
    and the validator exist to catch.

:class:`EvidenceSelectionError`
    A special case of the above, and its own type because ``PLAN.md`` names it
    explicitly: the reasoner selected evidence that retrieval never returned.
    The Agent may choose *among* the evidence, never *beyond* it, so an
    identifier that does not resolve is refused rather than dropped —
    silently discarding it is how a model's invented source becomes a
    published citation.

Deliberately **not** here: generation and verification failures.
``GenerationError`` and ``VerificationError`` pass straight through the agent
to the workflow, because a workflow records those as a failed phase and
``PLAN.md`` keeps that decision above this layer. Agent failures are the ones
that mean "the reasoning did not happen", and only those.
"""
from app.agent.enums import AgentFailureCategory
from app.errors import AppError

__all__ = [
    "AgentError",
    "EvidenceSelectionError",
    "ReasoningUnavailable",
    "UnusableReasoningAnswer",
]


class AgentError(AppError):
    """Base for everything that stops the Agent from producing a proposal.

    Carries an :class:`~app.agent.enums.AgentFailureCategory` so the workflow
    can record *why* without matching on a message — the same convention as
    :class:`~app.generation.errors.GenerationError` and
    :class:`~app.verification.errors.VerificationError`.
    """

    def __init__(self, message: str, *,
                 category: AgentFailureCategory = (
                     AgentFailureCategory.REASONING_UNAVAILABLE
                 )):
        super().__init__(message)
        self.category = category

    @property
    def is_publishable(self) -> bool:
        """Always ``False``, stated as a property so a caller can write the
        rule — *nothing that reaches here may publish* — without
        special-casing the exception."""
        return False


class ReasoningUnavailable(AgentError):
    """Raised by a reasoner that cannot produce an answer.

    Raised by :class:`~app.agent.llm.LlmContentReasoner` for everything that
    stops it answering — no credential, a client that will not build, a
    request that fails, a response nobody can parse. The deliberate mirror of
    :class:`~app.verification.errors.SupportJudgeUnavailable`, with one
    difference that matters: verification has a deterministic half to fall
    back on and calls that *degraded*; the Agent has nothing to fall back on,
    so this becomes ``DO_NOT_PUBLISH`` rather than a weaker proposal.
    """

    def __init__(self, message: str):
        super().__init__(
            message, category=AgentFailureCategory.REASONING_UNAVAILABLE
        )


class UnusableReasoningAnswer(AgentError):
    """Raised when the reasoner's answer cannot become a proposal.

    The answer *is* an answer; it is simply not usable. Distinct from
    :class:`ReasoningUnavailable` because a defect and an absence call for
    different repairs, and the same distinction
    :func:`app.verification.support.map_verdicts` draws about a judge.
    """

    def __init__(self, message: str):
        super().__init__(
            message, category=AgentFailureCategory.UNUSABLE_ANSWER
        )


class EvidenceSelectionError(AgentError):
    """Raised when the reasoner selects evidence the context does not hold.

    ``PLAN.md`` Step 10: *"The Agent may select evidence only from the
    evidence actually returned by retrieval/context. It may not invent source,
    chunk_id, claim, project, metric, citation."* Selection travels as labels
    — ``E1``, ``E2`` — which either resolve against the options this run
    actually built or do not exist, so "the Agent selected evidence it was not
    given" is a string comparison rather than a judgement call.
    """

    def __init__(self, message: str):
        super().__init__(
            message, category=AgentFailureCategory.EVIDENCE_SELECTION
        )
