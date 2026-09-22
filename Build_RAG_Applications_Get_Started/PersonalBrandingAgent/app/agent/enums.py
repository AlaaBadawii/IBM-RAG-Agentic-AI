"""Controlled vocabularies of the branding agent (``PLAN.md`` Step 10).

Same layout as every other layer's enums, and for the same reason: a value is
only useful downstream if it can be branched on, and it can only be branched on
if it is a closed set. A workflow deciding what to record and an alert deciding
whether to wake somebody must not have to read prose.

Three vocabularies, and each answers a question the layers above genuinely ask:

``AgentDecision``
    Did this run end with something to publish, or without? The asymmetry
    between the two members is the point of the whole package:
    ``DO_NOT_PUBLISH`` is an ordinary success (``PLAN.md`` Step 10), and
    ``PUBLISH`` is reachable *only* through a verification that passed —
    enforced in :meth:`app.agent.models.AgentResult.__post_init__`, so an
    agent that reports a publication it did not obtain fails loudly.

``NoPublishReason``
    Why there is no proposal to publish. Six of the seven are decided
    *before* a draft exists or *by* the deterministic gates afterwards; none
    of them is an error. They are separate values because a person reading an
    audit needs to tell "there was nothing to write about" from "the writer
    had nothing to say" from "the gate refused what was written".

``AgentFailureCategory``
    How the *reasoning* broke, when it did. Deliberately **not** a
    ``NoPublishReason``: a failure is what the future workflow notifies
    (``PLAN.md`` Step 10, Failure/recovery — the Agent itself sends nothing),
    and "the model was unreachable" is a different repair from "the model
    answered with something unusable" or "the model cited evidence retrieval
    never returned".
"""
from enum import Enum

__all__ = [
    "FAILURE_REASONS",
    "AgentDecision",
    "AgentFailureCategory",
    "NoPublishReason",
]


class AgentDecision(str, Enum):
    """What a run decided, once everything deterministic had its say."""

    #: A proposal to publish, which passed every gate on the way here.
    PUBLISH = "publish"

    #: No post. A normal, successful outcome with a reason attached — never
    #: an error, and never a silently empty result.
    DO_NOT_PUBLISH = "do_not_publish"


class NoPublishReason(str, Enum):
    """Why a run ended without a publication.

    Ordered the way a run proceeds: the first two are decided before any model
    is called, the next three during generation and reasoning, and the last two
    by the gates after a draft exists.
    """

    #: The assembled context carries no evidence at all — the shape Step 4
    #: produces when retrieval found only writing-style or positioning
    #: material. Decided deterministically, **without calling the model**:
    #: paying for a request the context has already answered is not a
    #: judgement call, and a model asked to write anyway is being invited to
    #: invent.
    NO_EVIDENCE = "no_evidence"

    #: The reasoner looked at the evidence and judged that there is not
    #: enough value in publishing anything from it. The Agent's own
    #: ``DO_NOT_PUBLISH``, and the answer ``PLAN.md` Step 10 exists to make
    #: reachable.
    NO_VALUE = "no_value"

    #: Generation declined: it was given evidence and reported that it does
    #: not support a post worth publishing. A result, not a failure.
    GENERATION_DECLINED = "generation_declined"

    #: Reasoning produced no answer — the model was unreachable, the client
    #: could not be built, or the answer was not the required shape. Carries
    #: an :class:`~app.agent.models.AgentFailure` for the workflow to notify.
    REASONING_FAILED = "reasoning_failed"

    #: The reasoner answered, and the answer could not become a proposal: a
    #: topic that is not an opportunity in this context, a retrieval strategy
    #: outside the allowed set, or no evidence selected at all. Carries an
    #: :class:`~app.agent.models.AgentFailure`.
    INVALID_PROPOSAL = "invalid_proposal"

    #: The deterministic gate rejected the draft outright — a finding that
    #: cannot be repaired by rewriting. ``PLAN.md``: ``REJECT`` is a decision,
    #: not a dead end.
    GATE_REJECTED = "gate_rejected"

    #: A revisable draft ran out of revision budget. Reported separately from
    #: ``GATE_REJECTED`` because "we stopped trying" and "this could never
    #: pass" are different facts about a run (``PLAN.md`` Step 9).
    REVISION_EXHAUSTED = "revision_exhausted"


class AgentFailureCategory(str, Enum):
    """How reasoning broke, so the workflow can notify without parsing text."""

    #: The reasoner could not be consulted: no client, no credential, a
    #: request that failed, or an answer nobody could parse. There is no
    #: degraded mode here — an agent that cannot reason cannot propose, and
    #: ``PLAN.md`` forbids falling back to publishing something weaker.
    REASONING_UNAVAILABLE = "reasoning_unavailable"

    #: The reasoner answered, and the answer is unusable: a topic that is not
    #: one of the context's opportunities, a strategy outside the allowed
    #: vocabulary, or no evidence selected. A defect rather than an absence.
    UNUSABLE_ANSWER = "unusable_answer"

    #: The reasoner selected evidence that retrieval never returned. The one
    #: failure ``PLAN.md`` Step 10 names explicitly: the Agent may choose
    #: *among* the evidence, never *beyond* it.
    EVIDENCE_SELECTION = "evidence_selection"


#: The reasons that are failures rather than decisions. ``AgentResult``
#: enforces that a failure is present exactly when the reason is one of these,
#: so "there is a failure to notify" and "this was a normal outcome" cannot
#: both be, or neither be, true of one object.
FAILURE_REASONS: frozenset[NoPublishReason] = frozenset({
    NoPublishReason.REASONING_FAILED,
    NoPublishReason.INVALID_PROPOSAL,
})
