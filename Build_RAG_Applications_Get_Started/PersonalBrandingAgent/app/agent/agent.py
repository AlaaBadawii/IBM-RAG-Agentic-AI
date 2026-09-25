"""The one bounded Agent (``PLAN.md`` Step 10).

``PLAN.md`` places it precisely: **above generation and verification, below
the workflows.** It reasons about content opportunities, topic, angle, evidence
selection, and whether there is enough value to publish at all. It proposes;
the workflow disposes.

    PersonalBrandingContext
        |
        +-- retrieve what there is to choose from (deterministic, no model)
        |
        +-- reason once  ----------------------> ContentReasoner
        |
        +-- resolve the answer against what was offered
        |       |                                    |
        |       +-- refused ------------------------> DO_NOT_PUBLISH
        |
        +-- PostGenerator -> EvidenceVerifier -> revision_decision
                (the bounded loop; every gate is somebody else's)

Four boundaries hold this together, and each is enforced rather than promised:

**One agent, no framework.** There is no graph, no planner, no critic, no
second model. ``reason`` is asked exactly once per run and there is no
mechanism by which it could be asked twice — the bounded part is the revision
loop *below* the decision, over drafts, and its bound belongs to
:func:`app.verification.revision.revision_decision`, which this module calls
rather than reimplements.

**The Agent proposes; the deterministic gates dispose.** A ``PUBLISH`` cannot
be constructed without a passing :class:`~app.verification.models.VerificationResult`
(``AgentResult.__post_init__``), and nothing in this package can publish
anything: there is no publisher, no store, no transport, and no import path to
any of them — the test suite asserts that by parsing these modules rather than
by trusting that no test looked. Step 9's own verifier is called as-is; not one
of its checks is duplicated or relaxed here.

**Evidence selection is confined to what retrieval returned.** The reasoner is
offered labels built from the context's own items, and its answer is resolved
against exactly that list. A label that does not resolve is
:class:`~app.agent.errors.EvidenceSelectionError` — refused, not dropped, and
the run ends as ``DO_NOT_PUBLISH`` rather than publishing a post whose citation
nobody can trace.

**Failure is not a fallback.** ``PLAN.md`` Step 10: *"Agent reasoning failure ->
``DO_NOT_PUBLISH`` plus a notification. Never a fallback that publishes
something weaker."* Every reasoning failure becomes a ``DO_NOT_PUBLISH``
result carrying an :class:`~app.agent.models.AgentFailure`; the Agent sends
nothing itself, because notifying is the workflow's.

Generation and verification failures are deliberately **not** caught here.
``GenerationError`` and ``VerificationError`` mean a phase of the run failed,
which ``PLAN.md`` keeps above this layer — the workflow records it, Step 7
notifies, and nothing is published. Collapsing those into ``DO_NOT_PUBLISH``
would report a broken run as a decision.
"""
from dataclasses import replace
from typing import Sequence

from app.agent.enums import (
    AgentDecision,
    AgentFailureCategory,
    NoPublishReason,
)
from app.agent.errors import (
    AgentError,
    EvidenceSelectionError,
    ReasoningUnavailable,
    UnusableReasoningAnswer,
)
from app.agent.history import (
    DEFAULT_DIGEST_LIMIT,
    PublicationHistoryReader,
    read_publication_history,
)
from app.agent.models import (
    AgentFailure,
    AgentProposal,
    AgentResult,
    EvidenceOption,
    HistoryDigest,
    ReasoningRequest,
    publishing_constraints,
)
from app.agent.prompt import (
    AGENT_PROMPT_VERSION,
    evidence_options,
    topic_candidates,
)
from app.context.models import PersonalBrandingContext
from app.logging_config import get_logger
from app.verification.models import VerificationRequest
from app.verification.revision import (
    MAX_REVISION_ATTEMPTS,
    RevisionDecision,
    revision_decision,
)

__all__ = ["BrandingAgent"]

logger = get_logger(__name__)


class BrandingAgent:
    """Reasons about what to publish, and drives the bounded loop that decides.

    Constructed once per workflow configuration. It holds the three things it
    is allowed to call — a reasoner, a generator and a verifier — plus the
    read-only history service, and it holds nothing else. There is no store
    handle, no publisher and no notifier anywhere in it.

    The collaborators are structural, not inherited, exactly as
    :class:`app.verification.support.SupportJudge` is: the test suite injects
    plain fakes and nothing has to be a framework type to participate.
    """

    def __init__(
        self,
        reasoner,
        generator,
        verifier,
        *,
        history: PublicationHistoryReader | None = None,
        strategies: Sequence[str] = ("vector", "bm25", "hybrid"),
        revision_limit: int = MAX_REVISION_ATTEMPTS,
        history_limit: int = DEFAULT_DIGEST_LIMIT,
        prompt_version: str = AGENT_PROMPT_VERSION,
        editorial_intent: str = "",
        withdrawn_publications: tuple[str, ...] = (),
    ):
        """
        Args:
            reasoner: a :class:`~app.agent.reasoning.ContentReasoner` — anything
                with ``name``, ``prompt_version`` and
                ``reason(request) -> ReasoningAnswer``.
            generator: a :class:`~app.generation.generator.PostGenerator`, or
                anything with the same ``generate(request)`` contract. Called,
                never reimplemented: the prompt that grounds a draft and the
                parsing that reads it back are Step 8's.
            verifier: an :class:`~app.verification.verifier.EvidenceVerifier`, or
                anything with the same ``verify(request)`` contract. Called,
                never reimplemented: every gate ``PLAN.md` Step 9 built stays
                exactly as authoritative inside the Agent as outside it.
            history: Step 6's read service, or ``None`` when there is no store
                to read. ``None`` yields an empty digest, which is what a first
                run has — never an error, and never a reason to refuse to
                publish the first post.
            strategies: the retrieval vocabulary the reasoner may choose from
                for a fresh pass at the chosen topic. The default is the three
                strategies that run locally with no further collaborator —
                ``vector``, ``bm25`` and ``hybrid``; ``app.retrieval.models``
                also has ``metadata``, ``multi_query`` and ``reranked``, which
                are left out by default because they need a filter, an LLM or a
                cross-encoder respectively. This must not be empty while the
                answer schema asks for ``"<a listed retrieval strategy>"``:
                :func:`~app.agent.prompt.build_reasoning_prompt` renders no
                RETRIEVAL STRATEGIES block for an empty tuple, so the model is
                asked to name one of nothing and every answer it can give is
                refused by :meth:`_proposal_from`. Empty is still accepted, and
                still means *no choice to make* — the proposal then keeps the
                strategy the context was assembled with, which is a real
                strategy that really produced this evidence rather than a
                default invented here. See :meth:`propose` for why choosing one
                is this step's at all.
            revision_limit: how many times a revisable draft may be rewritten
                before the run ends. Injectable so a caller with a different
                budget does not have to reimplement the stopping rule; passed
                straight to :func:`~app.verification.revision.revision_decision`,
                which owns the rule.
            history_limit: how many rows of each kind one digest carries.
            prompt_version: recorded on every proposal.
            withdrawn_publications: confirmed publication ids the owner
                later removed outside the system. Recorded on the digest as
                withdrawn (counts stay truthful) so the reasoner can see
                republishing those topics is legitimate. Empty means nothing
                was withdrawn, which is exactly how every existing caller
                behaves.
            editorial_intent: an objective for the writer, verbatim — e.g.
                the voice and shape a launch introduction should take. Carried
                on every generation request as a writing constraint (the
                documented purpose of ``PublishingConstraints.notes``), never
                interpreted here. Empty means no objective, which is exactly
                how every existing caller behaves.

        Raises:
            ValueError: ``revision_limit`` is negative. A negative budget is a
                caller defect, and guessing what it meant is how a stopping
                rule stops being one.
        """
        if revision_limit < 0:
            raise ValueError(
                f"revision_limit must not be negative, got {revision_limit}"
            )
        self._reasoner = reasoner
        self._generator = generator
        self._verifier = verifier
        self._history = history
        self._strategies = tuple(strategies)
        self._revision_limit = revision_limit
        self._history_limit = history_limit
        self._prompt_version = prompt_version
        self._withdrawn_publications = tuple(withdrawn_publications)
        self._editorial_intent = editorial_intent.strip()

    # -- what a caller uses -------------------------------------------------

    def propose(self, context: PersonalBrandingContext
                ) -> AgentProposal | AgentResult:
        """Decide what to write about, or decide not to write at all.

        Returns **either** the proposal — what to write about, which evidence
        to write from, and why — **or** the finished ``DO_NOT_PUBLISH`` result
        that ended the run before anything was written. A caller that only
        wants the outcome calls :meth:`run`; this exists so the decision can be
        inspected, tested and audited on its own, which is the half of a run
        that genuinely reasons.

        Two checks happen before the reasoner is asked anything, and both are
        deterministic:

        * a context with no evidence at all is ``NO_EVIDENCE`` — paying for a
          request the context has already answered is not a judgement call, and
          a model asked to write anyway is being invited to invent;
        * an **empty** ``evidence_options`` is the same case by another route,
          so the two cannot disagree.

        **Retrieval strategy selection lives here**, and only to the extent
        ``PLAN.md`` Step 10 asks for it: *"Topic and angle selection may use
        retrieval strategy selection — note that ``RetrievalEngine`` accepts a
        strategy but nothing currently chooses one."* The Agent does not
        retrieve and cannot — there is no path from this package to
        :mod:`app.retrieval`. What it produces is a *recommendation*: the
        strategy the workflow should use for a fresh pass at the topic it
        chose, drawn from the vocabulary the caller allowed. When the caller
        allows none, the proposal carries the strategy this context was
        assembled with, which is a strategy that demonstrably found this
        evidence.

        Raises:
            AgentError: never for a decision. See :meth:`run` — a reasoning
                failure is a result, and only a violated internal invariant
                raises out of this class.
        """
        return self._propose(
            context, read_publication_history(
                self._history, limit=self._history_limit,
                withdrawn_publication_ids=self._withdrawn_publications,
            )
        )

    def _propose(self, context: PersonalBrandingContext, history: HistoryDigest
                 ) -> AgentProposal | AgentResult:
        """The decision, with the history already read once for the whole run.

        Split out so :meth:`run` does not read the store twice: the digest a
        proposal was reasoned from and the digest its writing constraints came
        from are then the same value by construction rather than by two
        queries that happened to agree.
        """
        if context.is_insufficient or not context.evidence_items():
            return self._do_not_publish(
                NoPublishReason.NO_EVIDENCE,
                rationale=(
                    f"the assembled context carries no evidence "
                    f"(evidence status: {context.evidence_status.value})"
                ),
            )

        request = ReasoningRequest(
            context=context,
            topics=topic_candidates(context),
            evidence=evidence_options(context),
            history=history,
            strategies=self._strategies,
            prompt_version=self._prompt_version,
        )

        try:
            answer = self._reasoner.reason(request)
        except ReasoningUnavailable as exc:
            logger.warning("branding agent reasoning unavailable: %s", exc)
            return self._failed(
                NoPublishReason.REASONING_FAILED,
                AgentFailureCategory.REASONING_UNAVAILABLE,
                str(exc),
            )

        if not answer.publish:
            return self._do_not_publish(
                NoPublishReason.NO_VALUE,
                rationale=answer.decline_reason or answer.rationale
                or "the branding agent judged there is nothing worth "
                   "publishing from this context",
            )

        try:
            proposal = self._proposal_from(answer, request)
        except (UnusableReasoningAnswer, EvidenceSelectionError) as exc:
            logger.warning("branding agent produced an unusable answer: %s", exc)
            return self._failed(
                NoPublishReason.INVALID_PROPOSAL, exc.category, str(exc)
            )

        logger.info(
            "branding agent proposed topic=%s with %d evidence item(s) "
            "(strategy=%s)",
            proposal.topic, len(proposal.evidence), proposal.strategy,
        )
        return proposal

    def run(self, context: PersonalBrandingContext) -> AgentResult:
        """Propose, write, verify, and revise — boundedly — then decide.

        The whole bounded loop, and the only entry point a workflow needs:

        1. :meth:`propose` decides what to write about, or returns the finished
           ``DO_NOT_PUBLISH`` that ended the run.
        2. :class:`~app.generation.generator.PostGenerator` writes a draft from
           exactly the evidence the proposal selected. A decline is a
           ``DO_NOT_PUBLISH``; a ``GenerationError`` propagates.
        3. :class:`~app.verification.verifier.EvidenceVerifier` verifies the
           draft against the same context. A ``VerificationError`` propagates.
        4. :func:`~app.verification.revision.revision_decision` says what to do
           about the verdict, and **that function owns the bound**. ``REVISE``
           is returned only while the budget is unspent, so this loop runs at
           most ``revision_limit + 1`` times whatever the model does — which is
           what makes "bounded reasoning" a property of the code rather than of
           the prompt. A ``REVISE`` re-drives the generator with Step 9's own
           :meth:`~app.verification.models.VerificationResult.revision_notes`
           as writing constraints, which is why the second attempt is a
           bounded operation rather than a guess.

        **What this loop cannot do**, and the reason it is safe to call from
        anywhere: it cannot publish. It returns an :class:`AgentResult`, whose
        ``PUBLISH`` is unconstructible without a passing verification and which
        nothing in this package can turn into a LinkedIn call. Recording the
        publication is Step 11's; the Agent proposes.

        Raises:
            AgentError: a violated internal invariant — the loop outran its own
                bound, which :func:`revision_decision`'s contract makes
                unreachable. Raised rather than absorbed, because a stopping
                rule that stopped being one is not a decision.
            GenerationError: no draft exists and none can be produced. Not
                caught: there is no valid degraded post.
            VerificationError: the gate could not reach a verdict. Not caught:
                "the gate could not decide" is not a decision.
        """
        history = read_publication_history(
            self._history, limit=self._history_limit,
            withdrawn_publication_ids=self._withdrawn_publications,
        )
        proposal = self._propose(context, history)
        if isinstance(proposal, AgentResult):
            return proposal

        base = publishing_constraints(history)
        if self._editorial_intent:
            base = replace(
                base, notes=(*base.notes, self._editorial_intent))

        attempts_made = 0
        iterations = 0
        notes: tuple[str, ...] = ()

        while True:
            iterations += 1
            if iterations > self._revision_limit + 1:
                raise AgentError(
                    "the revision loop ran past its bound: "
                    "revision_decision() must not return REVISE once the "
                    "budget is spent, and a caller that obeys it cannot "
                    "reach this"
                )

            generated = self._generator.generate(
                proposal.generation_request(
                    constraints=replace(base, notes=(*base.notes, *notes))
                )
            )
            if generated.declined or generated.post is None:
                return self._do_not_publish(
                    NoPublishReason.GENERATION_DECLINED,
                    proposal=proposal,
                    attempts_made=attempts_made,
                    rationale=generated.decline_message
                    or "the writer did not produce a post from this evidence",
                )

            result = self._verifier.verify(
                VerificationRequest(post=generated.post, context=context)
            )
            decision = revision_decision(
                result, attempts_made, limit=self._revision_limit
            )

            if decision is RevisionDecision.PUBLISH:
                return AgentResult(
                    decision=AgentDecision.PUBLISH,
                    proposal=proposal,
                    draft=generated.post,
                    verification=result,
                    attempts_made=attempts_made,
                    rationale=proposal.rationale,
                )
            if decision is RevisionDecision.REJECT:
                return self._refused(
                    NoPublishReason.GATE_REJECTED, proposal, generated, result,
                    attempts_made,
                )
            if decision is RevisionDecision.EXHAUSTED:
                return self._refused(
                    NoPublishReason.REVISION_EXHAUSTED, proposal, generated,
                    result, attempts_made,
                )

            # REVISE: the verdict said what to change, and the budget allows it.
            attempts_made += 1
            notes = result.revision_notes()
            logger.info(
                "branding agent revising the draft (attempt %d/%d): %s",
                attempts_made, self._revision_limit, "; ".join(notes),
            )

    # -- resolution ---------------------------------------------------------

    def _proposal_from(self, answer, request: ReasoningRequest
                       ) -> AgentProposal:
        """Turn the reasoner's raw answer into a proposal, or refuse it.

        This is the only place a model's words become a fact about the world,
        and every one of them is checked against what the run actually built:

        * the **topic** must be one of the context's own non-empty evidence
          sections — a topic the evidence does not support is not a proposal;
        * every **evidence label** must resolve against the options this run
          offered, or the answer is refused rather than quietly trimmed;
        * the **strategy** must come from the vocabulary the caller allowed, or
          be absent, in which case the context's own strategy is kept.

        Raises:
            UnusableReasoningAnswer: the answer named something it was not
                offered, or decided to publish with nothing selected.
            EvidenceSelectionError: the answer selected evidence that
                retrieval never returned.
        """
        context = request.context

        if answer.topic is None:
            raise UnusableReasoningAnswer(
                "the branding agent decided to publish without naming a topic"
            )
        offered_topics = request.topics
        names = tuple(topic.name for topic in offered_topics)
        if answer.topic not in names:
            raise UnusableReasoningAnswer(
                f"the branding agent chose the topic {answer.topic!r}, which "
                f"is not one of this context's opportunities: {list(names)}"
            )

        if not answer.evidence_labels:
            raise UnusableReasoningAnswer(
                "the branding agent decided to publish without selecting any "
                "evidence; a post with nothing behind it is not a proposal"
            )

        options: dict[str, EvidenceOption] = {
            option.label: option for option in request.evidence
        }
        unknown = sorted({
            label for label in answer.evidence_labels
            if label not in options
        })
        if unknown:
            raise EvidenceSelectionError(
                f"the branding agent selected evidence retrieval did not "
                f"return: {unknown}. It was offered "
                f"{sorted(options)} and may select only from those."
            )

        # Resolve to the context's own items, in the context's order — the
        # same rule app.generation.prompt.selected_evidence applies, so a
        # repeated label is one piece of evidence and the prompt's labels do
        # not depend on the order the reasoner happened to list them in.
        selected = {
            options[label].identity for label in answer.evidence_labels
        }
        evidence = tuple(
            item for item in context.evidence_items()
            if (item.source, item.chunk_id) in selected
        )

        if answer.strategy is not None and answer.strategy not in self._strategies:
            raise UnusableReasoningAnswer(
                f"the branding agent chose the retrieval strategy "
                f"{answer.strategy!r}, which is not one of the "
                f"{len(self._strategies)} it was offered: "
                f"{list(self._strategies)}"
            )

        return AgentProposal(
            topic=answer.topic,
            context=context,
            evidence=evidence,
            angle=answer.angle,
            project=answer.project,
            strategy=answer.strategy or context.strategy,
            rationale=answer.rationale,
            prompt_version=getattr(
                self._reasoner, "prompt_version", self._prompt_version
            ),
            reasoner=getattr(self._reasoner, "name", type(self._reasoner).__name__),
        )

    # -- results ------------------------------------------------------------

    def _do_not_publish(self, reason: NoPublishReason, *, proposal=None,
                        attempts_made: int = 0, rationale: str = ""
                        ) -> AgentResult:
        """A decision not to publish. A success, with its reason attached."""
        return AgentResult(
            decision=AgentDecision.DO_NOT_PUBLISH,
            proposal=proposal,
            reason=reason,
            attempts_made=attempts_made,
            rationale=rationale,
        )

    def _failed(self, reason: NoPublishReason, category: AgentFailureCategory,
                detail: str) -> AgentResult:
        """``DO_NOT_PUBLISH`` because reasoning failed, with the failure kept.

        The one shape ``PLAN.md`` Step 10's Failure/recovery names: the run
        publishes nothing, and the failure travels so the workflow can notify
        it. The Agent itself sends nothing.
        """
        return AgentResult(
            decision=AgentDecision.DO_NOT_PUBLISH,
            reason=reason,
            failure=AgentFailure(category=category, detail=detail),
            rationale=detail,
        )

    def _refused(self, reason: NoPublishReason, proposal: AgentProposal,
                 generated, result, attempts_made: int) -> AgentResult:
        """``DO_NOT_PUBLISH`` because the gate refused a draft that exists.

        The proposal and the draft are kept: a run that wrote something and had
        it refused is a different audit entry from one that never wrote, and
        losing the distinction is how "we tried and it was rejected" becomes
        indistinguishable from "there was nothing to say".
        """
        return AgentResult(
            decision=AgentDecision.DO_NOT_PUBLISH,
            proposal=proposal,
            reason=reason,
            draft=generated.post,
            verification=result,
            attempts_made=attempts_made,
            rationale="; ".join(result.revision_notes())
            or f"verification returned {result.outcome.value}",
        )
