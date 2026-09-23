"""The shape of an agent run (``PLAN.md`` Step 10).

``PLAN.md`` splits the system in two: **the Agent proposes, the workflow
disposes.** These types are where that split is made structural rather than
rhetorical, in the same way :class:`app.verification.models.VerificationResult`
makes "a pass that carries a finding" unconstructible.

    * :class:`AgentProposal` is the *proposal* — what to write about, from
      which of the assembled context's evidence, and why. It cannot carry
      evidence the context does not hold, because it is built by resolving the
      reasoner's labels against the options this run actually built.
    * :class:`AgentResult` is the *outcome* — the decision, and everything
      behind it. Its ``__post_init__`` refuses to construct a ``PUBLISH`` that
      has no passing verification behind it, so an agent cannot claim a
      publication the deterministic gate did not grant.

Four absences are deliberate, and each is a thing this layer must not own:

* **No publisher and no store.** There is no handle, no session, no path to
  ``app.state`` or ``app.publishing.service`` anywhere in this package — the
  test suite asserts that by parsing the modules. ``PLAN.md`` Step 10: the
  Agent *"must not write to SQLite or publishing state"*, because recording is
  a deterministic workflow responsibility — *"or the system could forget to
  record"*.
* **No duplicate policy.** What has been published recently reaches the Agent
  as :class:`HistoryDigest`, a plain value the Agent is *told*, never a rule
  it applies. Overuse and near-duplicate detection stay in Step 6, over
  stored state, because they have to hold whether or not a model chose to
  respect them.
* **No quality score.** Step 9 owns verification; a number invented here would
  be a second, unverified opinion about a draft nothing has checked.
* **No clock and no environment.** ``to_record()`` is what a workflow records,
  so it holds only what the run produced.

The one place a model's answer becomes a fact is :class:`ReasoningAnswer`,
which is *raw*: it carries the labels and subjects the model named and nothing
resolved. Resolving them is
:meth:`app.agent.agent.BrandingAgent._proposal_from`, which can refuse. Keeping
the two apart is what makes "the Agent cannot invent a source" checkable.
"""
from dataclasses import dataclass, field
from typing import Any

from app.agent.enums import (
    FAILURE_REASONS,
    AgentDecision,
    AgentFailureCategory,
    NoPublishReason,
)
from app.context.models import ContextItem, PersonalBrandingContext
from app.generation.models import (
    GeneratedPost,
    GenerationRequest,
    PublishingConstraints,
)
from app.publishing.models import (
    EvidenceUsage,
    PublicationSummary,
    UsageCount,
)
from app.verification.models import VerificationResult

__all__ = [
    "AgentFailure",
    "AgentProposal",
    "AgentResult",
    "EvidenceOption",
    "HistoryDigest",
    "ReasoningAnswer",
    "ReasoningRequest",
    "TopicCandidate",
    "publishing_constraints",
]


# ------------------------------------------------------------------ inputs ---

@dataclass(frozen=True)
class TopicCandidate:
    """One content opportunity, derived deterministically from the context.

    A candidate is a **non-empty evidence section of this context** — the
    corpus's own vocabulary (``evidence``, ``completed_projects``,
    ``certificates``, …), not a topic invented by this layer or by the model.
    That is what makes "the Agent chose a topic the evidence does not support"
    structurally impossible: the reasoner picks from this tuple or the answer
    is refused.

    ``item_count`` and ``evidence_states`` are carried so a reasoner (and a
    person reading the prompt) can see how much stands behind each candidate
    without being handed the evidence text a second time.
    """

    name: str
    item_count: int
    evidence_states: frozenset[str] = frozenset()

    @property
    def is_declared(self) -> bool:
        """True when at least one item in this section declares an evidence
        state. Sections made only of unclassified material are still offered —
        they are what retrieval returned — but a reasoner can see the
        difference."""
        return bool(self.evidence_states)


@dataclass(frozen=True)
class EvidenceOption:
    """One piece of the context's evidence, under the label it is offered by.

    Identical in spirit to :class:`app.generation.models.EvidenceCitation`: the
    label is the interface between the model and the corpus, because a source
    path is something a model can invent and a label either resolves against
    the list that was sent or does not exist. Numbering starts at ``E1`` and
    runs in ``PersonalBrandingContext.evidence_items()`` order — the context's
    own deterministic order, so two runs over the same context offer the same
    labels.
    """

    label: str
    source: str
    chunk_id: str
    evidence_state: str | None
    section: str
    category: str = ""
    content: str = ""
    """The chunk exactly as stored. The reasoner judges publish-worthiness
    from substance, not from metadata alone: shown only a source path and an
    evidence state, it cannot tell "no evidence" from "evidence with no
    declared state"."""
    content_hash: str = ""
    """The chunk's content hash, so a decision stays attributable to the exact
    bytes it rested on."""

    @property
    def identity(self) -> tuple[str, str]:
        """``(source, chunk_id)`` — how a selected option is resolved back to
        the context item it came from."""
        return (self.source, self.chunk_id)


@dataclass(frozen=True)
class HistoryDigest:
    """What the Agent is told about its own past.

    Built by the caller from Step 6's read service
    (:class:`app.publishing.history.PublishingHistory`), never by querying the
    store — ``PLAN.md`` Step 10 is explicit about that. It is a *value* rather
    than the service itself for the same reason
    :class:`app.generation.models.PublishingConstraints` is: what crosses into
    the reasoning layer should be exactly what a model needs, and nothing else
    about the store should travel with it.

    Every row keeps its ``publication_ids``, so nothing here is an inference —
    a count the Agent reasons about can still be traced to stored publications
    afterwards. An empty digest is a normal answer: nothing has been published
    yet, which is the state of the system at its first run.
    """

    publications: tuple[PublicationSummary, ...] = ()
    topics: tuple[UsageCount, ...] = ()
    projects: tuple[UsageCount, ...] = ()
    evidence: tuple[EvidenceUsage, ...] = ()
    requires_review: tuple[PublicationSummary, ...] = ()

    @classmethod
    def empty(cls) -> "HistoryDigest":
        return cls()

    @property
    def is_empty(self) -> bool:
        return not (self.publications or self.topics or self.projects
                    or self.evidence or self.requires_review)

    @property
    def unresolved_ambiguity(self) -> bool:
        """True when an earlier attempt's outcome is still unknown.

        The Agent does not act on this — recovery is Step 6's, and a decision
        to withhold publishing because of an unresolved attempt is a
        *workflow* decision, not a reasoning one. It is here so a reasoner can
        see it and so an audit can explain a conservative proposal.
        """
        return bool(self.requires_review)


# ------------------------------------------------------------- the boundary ---

@dataclass(frozen=True)
class ReasoningRequest:
    """Everything the reasoner is asked, and nothing else.

    The context travels whole — it is the only evidence that exists as far as
    the Agent is concerned, and the reasoner is given the *options built from
    it* rather than a corpus handle. There is no retrieval call, no store and
    no network anywhere behind this type, which is what makes "the reasoner
    cannot consult evidence it was not shown" a property of the code.

    ``strategies`` is the retrieval vocabulary the caller allows for the
    *next* pass. Empty means "no choice to make": the proposal keeps the
    strategy this context was assembled with. See
    :mod:`app.agent.agent` for why choosing one is Step 10's at all.
    """

    context: PersonalBrandingContext
    topics: tuple[TopicCandidate, ...]
    evidence: tuple[EvidenceOption, ...]
    history: HistoryDigest
    strategies: tuple[str, ...] = ()
    prompt_version: str = ""


@dataclass(frozen=True)
class ReasoningAnswer:
    """What the reasoner said, exactly as it said it.

    Deliberately unresolved: ``topic`` is a string the model chose and
    ``evidence_labels`` are labels it named, both of which may be wrong.
    Nothing here is a fact about the world until
    :meth:`app.agent.agent.BrandingAgent._proposal_from` has resolved it
    against the request, and that resolution is where an invented source, a
    topic the context does not support, or a strategy outside the allowed set
    is refused rather than trusted.

    ``rationale`` and ``decline_reason`` are prose for a person. Nothing parses
    them, nothing branches on them, and neither is ever used to construct
    evidence — which is what keeps a model's explanation from becoming a
    source, the same rule the advisory judge follows in Step 9.
    """

    publish: bool
    topic: str | None = None
    angle: str | None = None
    project: str | None = None
    evidence_labels: tuple[str, ...] = ()
    strategy: str | None = None
    rationale: str = ""
    decline_reason: str = ""


# ---------------------------------------------------------------- outputs ---

@dataclass(frozen=True)
class AgentProposal:
    """What the Agent decided to write about, before anything was written.

    Resolution has already happened by the time one of these exists:
    ``evidence`` holds :class:`~app.context.models.ContextItem` objects taken
    from ``context`` itself, so
    :func:`app.generation.prompt.selected_evidence` finds every one of them in
    the context it is given. The proposal cannot smuggle in material the
    assembly layer never placed, and it does not have to be trusted not to —
    the layer below refuses it independently.

    ``strategy`` is the retrieval strategy to use for a *fresh* pass at this
    topic. It is carried rather than acted on: the Agent does not retrieve.
    """

    topic: str
    context: PersonalBrandingContext
    evidence: tuple[ContextItem, ...]
    angle: str | None = None
    project: str | None = None
    strategy: str = ""
    rationale: str = ""
    prompt_version: str = ""
    reasoner: str = ""
    """Which reasoner produced the decision, and which prompt version it was
    asked with — the same pair Step 9 records for the advisory judge, and for
    the same purpose: a decision that reads oddly later can be traced to what
    made it. The *model's* id travels with the draft instead
    (:class:`app.generation.models.GenerationMetadata`), where Step 8 requires
    it."""

    @property
    def evidence_keys(self) -> tuple[tuple[str, str], ...]:
        """``(source, chunk_id)`` for every selected item — how a proposal is
        compared against a context without either side being re-read."""
        return tuple((item.source, item.chunk_id) for item in self.evidence)

    def generation_request(self, *,
                           constraints: PublishingConstraints | None = None
                           ) -> GenerationRequest:
        """The deterministic generation request this proposal implies.

        A method rather than something the loop assembles inline, so "the
        Agent's decision becomes a generation task" is one readable line and
        every part of it is inspectable. The evidence is passed as an explicit
        subset, which is what makes the label round-trip checkable: the items
        came from this context, and
        :func:`app.generation.prompt.selected_evidence` re-checks it.
        """
        return GenerationRequest(
            context=self.context,
            topic=self.topic,
            angle=self.angle,
            project=self.project,
            evidence=self.evidence,
            constraints=constraints or PublishingConstraints(),
        )


@dataclass(frozen=True)
class AgentFailure:
    """A reasoning failure, in the form a workflow can notify.

    ``PLAN.md`` Step 10: the Agent *"expose[s] the failure so the future
    workflow can notify it"* and *"does not send notifications"*. This is that
    exposure — a category to branch on and a detail for a person, with no
    transport anywhere near it.
    """

    category: AgentFailureCategory
    detail: str


@dataclass(frozen=True)
class AgentResult:
    """The outcome of one run: a decision, and everything behind it.

    Constructed by :class:`app.agent.agent.BrandingAgent` and validated here.
    The invariant below is the whole reason this type exists rather than a
    tuple of values:

    **A ``PUBLISH`` cannot be constructed without a passing verification.**
    Not "should not" — cannot. So the one lie an agent could tell, reporting a
    publication the gate never granted, is a ``ValueError`` at construction
    instead of a post on LinkedIn.

    The converse is equally deliberate: a ``DO_NOT_PUBLISH`` **must** carry a
    reason, and ``proposal`` may or may not be set. A run that reasoned its way
    to a proposal and then had it refused by the gate is a different audit
    entry from one that never proposed anything, and both are successes.
    """

    decision: AgentDecision
    proposal: AgentProposal | None = None
    reason: NoPublishReason | None = None
    failure: AgentFailure | None = None
    draft: GeneratedPost | None = None
    verification: VerificationResult | None = None
    attempts_made: int = 0
    """Revisions attempted. Counts revisions, not verification calls, matching
    :func:`app.verification.revision.revision_decision`'s own definition."""

    rationale: str = ""

    def __post_init__(self) -> None:
        if self.attempts_made < 0:
            raise ValueError(
                f"attempts_made must not be negative, got {self.attempts_made}"
            )

        if self.decision is AgentDecision.PUBLISH:
            if self.verification is None:
                raise ValueError(
                    "a publish decision needs the verification that granted "
                    "it: the Agent proposes and the gate disposes, so there "
                    "is no path to PUBLISH that skips the gate"
                )
            if not self.verification.is_publishable:
                raise ValueError(
                    "a publish decision was built on a verification that did "
                    f"not pass (outcome: {self.verification.outcome.value})"
                )
            if self.reason is not None:
                raise ValueError(
                    f"a publish decision cannot also carry a no-publish "
                    f"reason ({self.reason.value})"
                )
            if self.failure is not None:
                raise ValueError(
                    "a publish decision cannot also carry a reasoning failure"
                )
            if self.proposal is None:
                raise ValueError(
                    "a publish decision needs the proposal it publishes"
                )
            return

        if self.reason is None:
            raise ValueError(
                "a do-not-publish decision must say why: PLAN.md requires "
                "DO_NOT_PUBLISH to be a first-class outcome, and an outcome "
                "with no reason is indistinguishable from a bug"
            )
        if (self.reason in FAILURE_REASONS) != (self.failure is not None):
            raise ValueError(
                f"a failure must be present exactly when the reason is a "
                f"failure: reason={self.reason.value}, "
                f"failure={self.failure is not None}"
            )

    # -- reading it ---------------------------------------------------------

    @property
    def is_publishable(self) -> bool:
        """True only for a decision the gate granted. The one question the
        workflow's publish path asks."""
        return (self.decision is AgentDecision.PUBLISH
                and self.verification is not None
                and self.verification.is_publishable)

    @property
    def failed(self) -> bool:
        """True when the *reasoning* failed. Distinct from ``not
        is_publishable`` on purpose: a ``DO_NOT_PUBLISH`` that the Agent
        decided is a success, and the workflow must not notify about it.
        """
        return self.failure is not None

    @property
    def has_proposal(self) -> bool:
        return self.proposal is not None

    @property
    def text(self) -> str:
        """The post, or an empty string. For callers that only need the text."""
        return self.draft.content if self.draft else ""

    def to_record(self) -> dict[str, Any]:
        """The recordable form, for the workflow (Step 11 writes it).

        Plain JSON-compatible values, no clock and no environment: the
        decision and its reason, the proposal's labels and evidence by
        provenance rather than by text, and Step 9's own record when a draft
        got that far. ``PLAN.md`` Step 10 keeps the *write* above this layer,
        so this stops at producing the value.
        """
        record: dict[str, Any] = {
            "decision": self.decision.value,
            "reason": self.reason.value if self.reason else None,
            "attempts_made": self.attempts_made,
            "rationale": self.rationale,
            "failure": (
                {
                    "category": self.failure.category.value,
                    "detail": self.failure.detail,
                }
                if self.failure else None
            ),
            "proposal": None,
            "verification": None,
        }
        if self.proposal is not None:
            record["proposal"] = {
                "topic": self.proposal.topic,
                "angle": self.proposal.angle,
                "project": self.proposal.project,
                "strategy": self.proposal.strategy,
                "prompt_version": self.proposal.prompt_version,
                "reasoner": self.proposal.reasoner,
                "evidence": [
                    {
                        "source": item.source,
                        "chunk_id": item.chunk_id,
                        "evidence_state": item.evidence_state,
                    }
                    for item in self.proposal.evidence
                ],
            }
        if self.verification is not None:
            record["verification"] = self.verification.to_record()
        return record


# ------------------------------------------------------------------ helpers ---

def publishing_constraints(history: HistoryDigest, *,
                           notes: tuple[str, ...] = ()
                           ) -> PublishingConstraints:
    """What the history means for a writer, as writing constraints.

    The same translation Step 8 anticipated when it typed
    ``PublishingConstraints`` as a plain value "the caller — Step 10's Agent,
    through Step 6's read service — hands over". Everything here is *what the
    person reading the post has already seen*: not a rule about what may be
    published. The duplicate policy is enforced by Step 6 over stored state,
    because it has to hold whether or not a model chose to respect it, and
    ``PLAN.md`` Step 10 forbids duplicating those gates inside the Agent.
    """
    return PublishingConstraints(
        recent_topics=tuple(row.value for row in history.topics),
        recent_projects=tuple(row.value for row in history.projects),
        recent_angles=tuple(
            summary.angle for summary in history.publications
            if summary.angle
        ),
        notes=tuple(notes),
    )
