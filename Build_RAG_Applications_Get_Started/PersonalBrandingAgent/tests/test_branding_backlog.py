"""The branding workflow over the persistent backlog: multi-publish behavior.

Runs the real workflow (default persist/backlog/claim/context bindings
against a temporary store) with fakes only at the established seams —
context assembly, the agent, per-opportunity publishing, notifications —
plus real assembled contexts where discovery persistence is under test.

Covers: all discoveries persisted; unselected rows stay queued; cross-run
survival when retrieval omits them; the two-publish bound; failure
isolation; duplicate discovery; gate/generator semantics; ambiguous
publications blocking later runs; crash-triage of intents; stale-claim
recovery; and the persisted no-publish reason.
"""
from dataclasses import dataclass

from app.agent.enums import AgentDecision, NoPublishReason
from app.agent.models import AgentResult
from app.context.enums import EvidenceStatus
from app.context.models import (
    ContextCoverage,
    ContextItem,
    ContextSection,
    PersonalBrandingContext,
    SectionCoverage,
    SourceStateReport,
)
from app.notify.enums import NotificationDecision
from app.notify.models import NotificationReport
from app.publishing.enums import PublishDecision
from app.publishing.service import MAX_PUBLISHES_PER_RUN
from app.state import OpportunityStatus, RunOutcome, StateStore
from app.workflows import BrandingConfig, run_branding
from app.workflows.branding import MAX_DECISIONS_PER_RUN


# ------------------------------------------------------------------ fakes ---

@dataclass
class FakeDraft:
    content: str


@dataclass
class FakeProposal:
    topic: str
    angle: str | None = None
    project: str | None = None
    evidence: tuple = ()


@dataclass
class PublishableStub:
    """A publishable result shaped like the workflow's real input."""

    text: str = "A grounded post."
    topic: str = "projects"
    failed: bool = False
    is_publishable: bool = True
    reason: object = None
    attempts_made: int = 0
    draft: object = None
    proposal: object = None

    def __post_init__(self):
        self.draft = FakeDraft(self.text)
        self.proposal = FakeProposal(self.topic)


def declined_result(reason=NoPublishReason.NO_VALUE):
    return AgentResult(decision=AgentDecision.DO_NOT_PUBLISH, reason=reason)


class TopicAgent:
    """Returns a per-topic publishable stub, or declines named topics."""

    def __init__(self, decline=()):
        self.decline = set(decline)
        self.calls: list = []

    def run(self, context):
        self.calls.append(context)
        sections = getattr(context, "evidence_sections", ())
        topic = sections[0].name if sections else "unknown"
        if topic in self.decline:
            return declined_result()
        return PublishableStub(
            text=f"A grounded post about {topic}.", topic=topic)


@dataclass
class FakeBacklogReport:
    decision: PublishDecision = PublishDecision.PUBLISHED
    message: str = "published"
    post_id: str | None = "post_1"
    publication: object = None

    @property
    def published(self):
        return self.decision is PublishDecision.PUBLISHED

    @property
    def refused(self):
        return self.decision is PublishDecision.REFUSED

    @property
    def requires_review(self):
        return self.decision is PublishDecision.UNKNOWN_REQUIRES_REVIEW

    @property
    def requires_human_intervention(self):
        return self.requires_review

    @property
    def linkedin_post_id(self):
        return self.post_id


class CapturingNotifier:
    def __init__(self, store):
        self.store = store
        self.run_calls: list[str] = []
        self.publication_calls: list = []
        self.no_publish_calls: list = []

    def notify_run(self, run_id):
        self.run_calls.append(run_id)
        return NotificationReport(
            decision=NotificationDecision.SENT, message=f"notified {run_id}")

    def notify_publication(self, post, *, run_id=None):
        self.publication_calls.append((post, run_id))
        return NotificationReport(
            decision=NotificationDecision.SENT, message="reported")

    def notify_no_publish(self, notice, *, run_id=None):
        self.no_publish_calls.append((notice, run_id))
        return NotificationReport(
            decision=NotificationDecision.SENT, message="reported no publish")


def make_context(topics):
    """A real assembled-shape context with one section per topic."""
    sections = []
    for order, topic in enumerate(topics):
        item = ContextItem(
            content=f"Evidence substance for {topic}.",
            source=f"evidence/{topic}.md",
            chunk_id=f"hash-{topic}:0",
            evidence_state="DOCUMENTED",
            category="evidence",
            document_type=None,
            metadata={"content_hash": f"hash-{topic}",
                      "category": "evidence"},
            strategy="vector",
            rank=1,
            score=1.0,
        )
        sections.append(ContextSection(
            name=topic,
            order=order,
            items=(item,),
            coverage=SectionCoverage(
                item_count=1,
                evidence_states_present=frozenset({"DOCUMENTED"}),
                unclassified_count=0),
        ))
    names = tuple(topics)
    return PersonalBrandingContext(
        query="recent work",
        strategy="vector",
        evidence_status=(EvidenceStatus.SUFFICIENT if sections
                         else EvidenceStatus.INSUFFICIENT),
        evidence_sections=tuple(sections),
        guidance_sections=(),
        coverage=ContextCoverage(
            evidence_item_count=len(sections),
            guidance_item_count=0,
            populated_sections=names,
            empty_sections=(),
            evidence_states_present=frozenset({"DOCUMENTED"}),
            unclassified_count=0),
        source_state=SourceStateReport(sources=()),
    )


def backlog_config(tmp_path, *, contexts, agent=None,
                   publish_reports=None, publish_calls=None,
                   publish_raises=None, transports=None,
                   db_name="backlog.db"):
    """The real workflow with fakes at the established seams only.

    ``transports`` routes publishing through the real
    ``PublishingService`` with one fake transport callable per expected
    attempt — so intents, publications, and duplicate gates are real
    store rows rather than report-shaped fakes.
    """
    holder: dict = {}
    agent = agent if agent is not None else TopicAgent()
    queue = list(contexts)

    def fake_assemble(_store):
        return queue.pop(0) if queue else make_context([])

    def fake_publish_one(agent_result, run_id, _store, opportunity):
        (publish_calls if publish_calls is not None else []).append(
            (run_id,
             opportunity.opportunity_id if opportunity is not None else None))
        if publish_raises is not None:
            raise publish_raises
        if transports is not None:
            from app.publishing import PublishingService
            from app.workflows.branding import _build_publish_request
            service = PublishingService(
                _store, transport=transports.pop(0))
            return service.publish(
                _build_publish_request(
                    agent_result,
                    opportunity.opportunity_id
                    if opportunity is not None else None),
                run_id)
        if publish_reports:
            return publish_reports.pop(0)
        return FakeBacklogReport(
            post_id=f"post_{agent_result.proposal.topic}")

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    cfg = BrandingConfig(
        store_factory=lambda: StateStore(tmp_path / db_name),
        assemble_fn=fake_assemble,
        agent_factory=lambda _store: agent,
        publish_one_fn=fake_publish_one,
        notifier_factory=fake_notifier,
    )
    return cfg, holder, agent


def open_store(tmp_path, db_name="backlog.db"):
    return StateStore(tmp_path / db_name)


def backlog_rows(tmp_path, db_name="backlog.db"):
    with open_store(tmp_path, db_name) as store:
        return store.list_backlog(limit=50)


def stored_run(tmp_path, run_id, db_name="backlog.db"):
    with open_store(tmp_path, db_name) as store:
        return store.get_run(run_id)


# --------------------------------------------------------------- persist ---

def test_all_discoveries_are_persisted_before_selection(tmp_path):
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])],
        agent=TopicAgent(decline={"aaa", "bbb", "ccc"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    rows = {o.topic: o for o in backlog_rows(tmp_path)}
    assert sorted(rows) == ["aaa", "bbb", "ccc"]
    assert all(o.status is OpportunityStatus.QUEUED for o in rows.values())
    # Only the two claimed selections were evaluated; the third row was
    # never touched — not selected is not a decision about it.
    assert rows["aaa"].attempts == 1
    assert rows["bbb"].attempts == 1
    assert rows["ccc"].attempts == 0
    assert rows["ccc"].last_decision is None
    assert result.detail["considered"] == 3
    assert result.detail["selected"] == 0
    assert result.detail["queued_remaining"] == 3


def test_quiet_backlog_notice_carries_backlog_snapshot(tmp_path):
    """The quiet-run notice says what was tried and what remains queued."""
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])],
        agent=TopicAgent(decline={"aaa", "bbb", "ccc"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.considered == 3
    assert notice.selected == 0
    assert notice.queued_remaining == 3
    assert len(notice.deferred) == 2
    assert any("aaa" in entry for entry in notice.deferred)
    assert any("bbb" in entry for entry in notice.deferred)


def test_quiet_backlog_run_records_its_reason_on_the_run(tmp_path):
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TopicAgent(decline={"aaa"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    run = stored_run(tmp_path, result.run_id)
    assert run.no_publish_reason == NoPublishReason.NO_VALUE.value
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.reason == NoPublishReason.NO_VALUE.value


def test_unclaimable_backlog_run_records_no_value_on_the_run(tmp_path):
    """B1: rows exist but none could be claimed — still NO_VALUE, not NULL."""
    pool = [object(), object()]
    holder: dict = {}

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    cfg = BrandingConfig(
        store_factory=lambda: StateStore(tmp_path / "unclaimable.db"),
        assemble_fn=lambda _store: object(),
        agent_factory=lambda _store: object(),  # never consulted: none claimed
        persist_fn=lambda _store, _context: [],
        backlog_fn=lambda _store, _run_id: list(pool),
        claim_fn=lambda _store, _run_id, _limit: [],
        notifier_factory=fake_notifier,
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.detail.get("no_publish_reason") == (
        NoPublishReason.NO_VALUE.value
    )
    run = stored_run(tmp_path, result.run_id, db_name="unclaimable.db")
    assert run.no_publish_reason == NoPublishReason.NO_VALUE.value
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.reason == NoPublishReason.NO_VALUE.value


def test_all_refused_backlog_run_keeps_refusal_detail_with_no_value(tmp_path):
    """Backlog refusal pin (decision (c)): every selection refused at the
    duplicate gate. The column records NO_VALUE while detail preserves the
    refusal — deliberately not harmonized with the single-shot S2 NULL."""
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TopicAgent(),
        publish_reports=[FakeBacklogReport(
            decision=PublishDecision.REFUSED,
            post_id=None,
            message="exact_duplicate: this text already went out",
        )])
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.detail.get("refused") is True
    run = stored_run(tmp_path, result.run_id)
    assert run.no_publish_reason == NoPublishReason.NO_VALUE.value
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.refused is True
    assert notice.refusal == "exact_duplicate: this text already went out"


def test_rediscovery_does_not_duplicate_the_backlog(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path,
        contexts=[make_context(["aaa", "bbb"]),
                  make_context(["aaa", "bbb"])],
        agent=TopicAgent(decline={"aaa", "bbb"}))
    run_branding(cfg)
    run_branding(cfg)

    rows = backlog_rows(tmp_path)
    assert sorted(o.topic for o in rows) == ["aaa", "bbb"]


# ------------------------------------------------------------- selection ---

def _transport(post_id=None, outcome=None):
    """One fake LinkedIn transport returning a canned result."""
    from app.integrations.linkedin.enums import PublicationOutcome
    from app.integrations.linkedin.models import PublicationResult

    def send(text):
        return PublicationResult(
            outcome=(outcome if outcome is not None
                     else PublicationOutcome.PUBLISHED),
            message="ok" if post_id else "no id",
            api_version="202607",
            attempted_at="2026-09-26T00:00:00+00:00",
            post_id=post_id)
    return send


def test_one_publish_bound_with_siblings_left_queued(tmp_path):
    """A run publishes one post; a second verified sibling is released, not
    sent and not lost, and a third claimed-less row is never touched."""
    assert MAX_PUBLISHES_PER_RUN == 1
    assert MAX_DECISIONS_PER_RUN == 2
    calls: list = []
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])],
        publish_calls=calls,
        transports=[_transport("urn:li:share:aaa"),
                    _transport("urn:li:share:bbb")])
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert len(calls) == 1, "more than one publish attempt in a single run"
    assert result.detail["considered"] == 3
    assert result.detail["selected"] == 2
    assert result.detail["published_count"] == 1
    assert result.detail["queued_remaining"] == 2
    assert len(holder["notifier"].publication_calls) == 1
    assert holder["notifier"].run_calls == []

    rows = {o.topic: o for o in backlog_rows(tmp_path)}
    assert sorted(rows) == ["bbb", "ccc"]
    # The verified-but-unpublished sibling was released for a later run: it is
    # queued, unpenalized (the decision succeeded — only the budget ran out).
    assert rows["bbb"].attempts == 0
    assert rows["ccc"].attempts == 0
    assert rows["ccc"].last_decision is None
    with open_store(tmp_path) as store:
        assert len(store.list_publications(limit=10)) == 1
        intents = store.list_publish_intents(limit=10)
        assert len(intents) == 1
        assert {i.opportunity_id for i in intents} == {calls[0][1]}


def test_unselected_rows_are_untouched_not_consumed(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])])
    run_branding(cfg)

    rows = {o.topic: o for o in backlog_rows(tmp_path)}
    # Only the two claimed selections were evaluated; the third row was never
    # touched — not selected is not a decision about it.
    assert sorted(rows) == ["bbb", "ccc"]
    assert rows["ccc"].attempts == 0
    assert rows["ccc"].last_decision is None


def test_claim_is_bounded_by_the_decision_limit(tmp_path):
    seen: list = []

    def capturing_claim(store, run_id, limit):
        seen.append(limit)
        return store.claim_opportunities(run_id, limit)

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])])
    cfg.claim_fn = capturing_claim
    run_branding(cfg)

    assert seen == [MAX_DECISIONS_PER_RUN]


# ------------------------------------------------------------- cross-run ---

def test_queued_survives_when_retrieval_omits_it(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path,
        contexts=[make_context(["aaa", "bbb", "ccc"]),
                  make_context([])],
        agent=TopicAgent(decline={"aaa", "bbb", "ccc"}))
    first = run_branding(cfg)
    assert first.detail["queued_remaining"] == 3

    # Run 2 rediscovers nothing — yet the backlog still selects and
    # publishes from the older queued opportunities.
    cfg2, holder2, _ = backlog_config(
        tmp_path, contexts=[make_context([])], db_name="backlog.db")
    second = run_branding(cfg2)

    assert second.outcome is RunOutcome.DO_NOT_PUBLISH
    assert second.detail["selected"] == 2
    assert second.detail["published_count"] == 1
    assert second.detail["queued_remaining"] == 2
    assert len(holder2["notifier"].publication_calls) == 1


# ------------------------------------------------------ failure handling ---

def test_one_failure_does_not_corrupt_its_sibling(tmp_path):
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb", "ccc"])],
        publish_reports=[
            FakeBacklogReport(
                decision=PublishDecision.FAILED, post_id=None,
                message="LinkedIn refused the request"),
        ])
    result = run_branding(cfg)

    # One publish attempt per run: the failure ends the attempt and fails the
    # run, and the sibling that was never attempted returns to the backlog
    # rather than being corrupted or dropped.
    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.failed_phase == "publish"
    assert holder["notifier"].run_calls == [result.run_id]
    assert holder["notifier"].no_publish_calls == []

    rows = {o.topic: o for o in backlog_rows(tmp_path)}
    assert set(rows) == {"aaa", "bbb", "ccc"}
    assert rows["aaa"].attempts == 1
    assert rows["aaa"].last_decision == "publish_failed"
    assert rows["bbb"].attempts == 0
    assert rows["ccc"].attempts == 0


def test_all_selections_failing_is_a_workflow_failure(tmp_path):
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        publish_reports=[
            FakeBacklogReport(
                decision=PublishDecision.FAILED, post_id=None,
                message="LinkedIn refused the request"),
        ])
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.failed_phase == "publish"
    assert holder["notifier"].run_calls == [result.run_id]
    assert holder["notifier"].no_publish_calls == []
    rows = backlog_rows(tmp_path)
    assert len(rows) == 1 and rows[0].status is OpportunityStatus.QUEUED


def test_a_run_records_each_claimed_opportunitys_terminal_outcome(tmp_path):
    """A failed run persists what each opportunity it tried ended as, so the
    notification can enumerate them without opening the backlog (§12 P3.1)."""
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        publish_reports=[
            FakeBacklogReport(
                decision=PublishDecision.FAILED, post_id=None,
                message="LinkedIn refused the request"),
        ])
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    with open_store(tmp_path) as store:
        outcomes = store.list_opportunity_outcomes(result.run_id)
    assert len(outcomes) == 1
    assert outcomes[0].topic == "aaa"
    assert outcomes[0].decision == "publish_failed"
    assert "refused the request" in outcomes[0].rationale


def test_a_declined_opportunitys_outcome_keeps_its_reason(tmp_path):
    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TopicAgent(decline={"aaa"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    with open_store(tmp_path) as store:
        outcomes = store.list_opportunity_outcomes(result.run_id)
    assert len(outcomes) == 1
    assert outcomes[0].topic == "aaa"
    assert outcomes[0].decision == "deferred"
    assert outcomes[0].rationale == "no_value"


def test_a_published_opportunitys_outcome_carries_its_selection_trace(tmp_path):
    class TracingAgent(TopicAgent):
        def run(self, context):
            result = super().run(context)
            sections = getattr(context, "evidence_sections", ())
            item = sections[0].items[0] if sections else None
            if item is not None:
                result.proposal.evidence_keys = ((item.source, item.chunk_id),)
            return result

    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TracingAgent(),
        publish_reports=[FakeBacklogReport(post_id="post_aaa")])
    result = run_branding(cfg)

    with open_store(tmp_path) as store:
        outcomes = store.list_opportunity_outcomes(result.run_id)
    assert len(outcomes) == 1
    assert outcomes[0].decision == "published"
    assert outcomes[0].trace, "the chosen chunks are recorded (§12 P3.3)"
    assert outcomes[0].trace[0] == {
        "source": "evidence/aaa.md", "chunk_id": "hash-aaa:0", "rank": 0,
    }


def test_gate_rejection_is_terminal_but_sibling_safe(tmp_path):
    from app.agent.enums import NoPublishReason as Reason

    class RejectingAgent(TopicAgent):
        def run(self, context):
            sections = getattr(context, "evidence_sections", ())
            topic = sections[0].name if sections else "unknown"
            if topic == "aaa":
                return AgentResult(
                    decision=AgentDecision.DO_NOT_PUBLISH,
                    reason=Reason.GATE_REJECTED,
                    rationale="citation unsupported and unrepairable")
            return super().run(context)

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb"])],
        agent=RejectingAgent())
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.detail["published_count"] == 1
    with open_store(tmp_path) as store:
        rejected = list(store._read(
            "SELECT * FROM content_opportunities WHERE status = 'rejected'"))
        assert [row["topic"] for row in rejected] == ["aaa"]
        assert store.count_backlog() == 0


def test_generation_decline_returns_the_row_as_retryable(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TopicAgent(decline={"aaa"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    rows = backlog_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].status is OpportunityStatus.QUEUED
    assert rows[0].attempts == 1
    assert rows[0].last_decision == "deferred"


def test_duplicate_refusal_returns_the_row_as_retryable(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        publish_reports=[
            FakeBacklogReport(
                decision=PublishDecision.REFUSED, post_id=None,
                message="exact_duplicate: this text already went out"),
        ])
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    rows = backlog_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].last_decision == "duplicate"


# --------------------------------------------------------------- ambiguity ---

def test_ambiguous_publication_blocks_and_locks_its_row(tmp_path):
    from app.integrations.linkedin.enums import PublicationOutcome

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa", "bbb"])],
        transports=[
            _transport(post_id=None, outcome=PublicationOutcome.UNKNOWN),
            _transport("urn:li:share:bbb"),
        ])
    result = run_branding(cfg)

    # One publish attempt per run: the first candidate's ambiguous outcome
    # ends the attempt and escalates. The sibling is released, never sent.
    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.detail["published_count"] == 0
    assert result.detail["requires_review"] == 1
    with open_store(tmp_path) as store:
        by_status = {}
        for row in store._read("SELECT * FROM content_opportunities"):
            by_status.setdefault(row["status"], []).append(row["topic"])
        assert by_status["requires_review"] == ["aaa"]
        assert by_status["queued"] == ["bbb"]

    # A later run refuses to publish over the ambiguity — even for the
    # other queued row — until a person resolves it.
    calls: list = []
    cfg2, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["ccc"])], publish_calls=calls)
    rerun = run_branding(cfg2)
    assert rerun.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert calls == []


# ----------------------------------------------------------------- crash ---

def test_publish_crash_with_intent_started_blocks_republish(tmp_path):
    from app.state import PublishState

    def crash_after_start(agent_result, run_id, store, opportunity):
        intent = store.create_publish_intent(
            run_id, agent_result.draft.content,
            opportunity_id=opportunity.opportunity_id, max_per_run=99)
        store.mark_attempt_started(intent.intent_id)
        raise RuntimeError("process died mid-request")

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        publish_raises=RuntimeError("process died mid-request"))
    # Replace the raising fake with one that leaves a started intent: the
    # honest residue of a crash after the request left the machine.
    cfg.publish_one_fn = crash_after_start
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    with open_store(tmp_path) as store:
        rows = store._read("SELECT * FROM content_opportunities")
        assert rows[0]["status"] == "requires_review"
        intents = store.list_intents_for_run(result.run_id)
        assert intents[0].state is PublishState.ATTEMPT_STARTED


def test_publish_crash_before_any_request_is_retryable(tmp_path):
    from app.state import PublishState

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        publish_raises=RuntimeError("transport exploded"))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    with open_store(tmp_path) as store:
        rows = store._read("SELECT * FROM content_opportunities")
        assert rows[0]["status"] == "queued"
        assert "publish_failed" in (rows[0]["last_decision"] or "")
        intents = store.list_intents_for_run(result.run_id)
        assert all(i.state is PublishState.FAILED for i in intents) or \
            intents == []


def test_finished_runs_stale_claims_are_recovered_on_the_next_run(tmp_path):
    with open_store(tmp_path) as store:
        from app.opportunities.backlog import persist_discoveries
        persisted = persist_discoveries(store, make_context(["aaa"]))
        crashed = store.start_run("branding")
        store.finish_run(crashed.run_id, RunOutcome.DO_NOT_PUBLISH)
        store.claim_opportunities(crashed.run_id, 2)
        assert store.get_opportunity(
            persisted[0].opportunity_id).status is OpportunityStatus.CLAIMED

    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context([])],
        agent=TopicAgent(decline={"aaa"}))
    result = run_branding(cfg)

    # The stale claim was recovered into the pool and then evaluated in
    # the same run: released by recovery, claimed, declined, deferred.
    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    rows = backlog_rows(tmp_path)
    assert len(rows) == 1 and rows[0].status is OpportunityStatus.QUEUED
    assert rows[0].attempts == 1
    assert rows[0].last_decision == "deferred"


# -------------------------------------------------------------- freshness ---

def test_changed_evidence_is_a_new_opportunity_not_a_rewrite(tmp_path):
    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["aaa"])],
        agent=TopicAgent(decline={"aaa"}))
    run_branding(cfg)

    redrafted = make_context(["aaa"])
    for section in redrafted.evidence_sections:
        for item in section.items:
            object.__setattr__(item, "chunk_id", "hash-aaa-v2:0")
            item.metadata["content_hash"] = "hash-aaa-v2"
    cfg2, _, _ = backlog_config(
        tmp_path, contexts=[redrafted], agent=TopicAgent(decline={"aaa"}))
    run_branding(cfg2)

    assert len(backlog_rows(tmp_path)) == 2


# ------------------------------------------------------- retirement ---

def test_declined_opportunity_retires_once_its_budget_is_spent(tmp_path):
    from app.opportunities.backlog import persist_discoveries

    with open_store(tmp_path) as store:
        row = persist_discoveries(store, make_context(["stuck"]))[0]
        for _ in range(3):
            store.record_opportunity_decision(
                row.opportunity_id, "deferred", attempts_increment=1)

    cfg, holder, _ = backlog_config(
        tmp_path, contexts=[make_context([])],
        agent=TopicAgent(decline={"stuck"}))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    # Rounding its budget on the current snapshot policy retires it as an
    # explicit ``exhausted`` decision — not a silent disappearance.
    with open_store(tmp_path) as store:
        stored = store.get_opportunity(row.opportunity_id)
        assert stored.status is OpportunityStatus.EXHAUSTED
        assert stored.attempts == 4
        assert stored.last_decision == "exhausted"
        assert "retired after 4 attempt(s)" in (stored.last_error or "")
    assert backlog_rows(tmp_path) == []


def test_declined_opportunity_with_a_stale_snapshot_is_released_not_retired(
        tmp_path):
    from app.opportunities.backlog import persist_discoveries

    with open_store(tmp_path) as store:
        row = persist_discoveries(store, make_context(["stuck"]))[0]
        for _ in range(3):
            store.record_opportunity_decision(
                row.opportunity_id, "deferred", attempts_increment=1)
        store._conn.execute("UPDATE content_opportunities "
                            "SET snapshot_version = 1, snapshot_hash = ''")
        store._conn.commit()

    # A later run discovers a different topic, so ``stuck`` is claimed from
    # the backlog but never refreshed by discovery.
    cfg, _, _ = backlog_config(
        tmp_path, contexts=[make_context(["other"])],
        agent=TopicAgent(decline={"stuck", "other"}))
    run_branding(cfg)

    # A stale snapshot is a repairable defect, not proof the row is
    # unpostable: it is released so the refresh/repair path can heal it.
    with open_store(tmp_path) as store:
        stored = store.get_opportunity(row.opportunity_id)
        assert stored.status is OpportunityStatus.QUEUED
        assert stored.attempts == 4
        assert stored.last_decision == "deferred"
