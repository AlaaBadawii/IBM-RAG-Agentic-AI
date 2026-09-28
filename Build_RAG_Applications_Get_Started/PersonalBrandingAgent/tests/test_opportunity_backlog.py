"""The persistent content-opportunity backlog: store and fingerprint contract.

Covers the durable layer the multi-publish workflow stands on: idempotent
enqueue by stable fingerprint, anti-starvation backlog order, atomic claims
(including across two overlapping store handles), ownership-guarded release
and finalization, stale-claim recovery from recorded intent outcomes, and
the per-run publish-intent limit (application check plus trigger backstop).

All state is isolated per test (temporary stores); the production database
is never touched.
"""
import pytest

from app.errors import StateConstraintError, StateStoreError
from app.opportunities.backlog import (
    OpportunityDecision,
    build_opportunity_context,
    evidence_snapshot,
    opportunity_fingerprint,
    persist_discoveries,
)
from app.state import (
    SCHEMA_VERSION,
    OpportunityStatus,
    PublishState,
    StateStore,
)


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "backlog.db") as state:
        yield state


def _evidence(source="evidence/work.md", digest="abc123", index=0):
    return {
        "source": source,
        "chunk_id": f"{digest}:{index}",
        "content_hash": digest,
        "evidence_state": "DOCUMENTED",
        "category": "evidence",
        "document_type": None,
        "content": f"content of {source}#{index}",
    }


def _enqueue(store, topic, digests=("abc123",), **kwargs):
    evidence = [_evidence(digest=d, index=i) for i, d in enumerate(digests)]
    fingerprint = opportunity_fingerprint(
        topic, [(e["source"], e["content_hash"]) for e in evidence])
    return store.enqueue_opportunity(fingerprint, topic, evidence, **kwargs)


# ------------------------------------------------------------- identity ---

def test_schema_is_at_v9_with_the_backlog_table(store):
    assert SCHEMA_VERSION == 9
    assert store.schema_version == 9
    tables = {
        row[0] for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "content_opportunities" in tables


def test_fingerprint_is_stable_and_evidence_sensitive():
    base = [("evidence/a.md", "hash1"), ("evidence/b.md", "hash2")]
    assert opportunity_fingerprint("topic", base) == \
        opportunity_fingerprint("topic", list(reversed(base)))
    assert opportunity_fingerprint("topic", base) != \
        opportunity_fingerprint("topic", [("evidence/a.md", "hash1")])
    assert opportunity_fingerprint("topic", base) != \
        opportunity_fingerprint("other", base)
    assert opportunity_fingerprint("topic", base) != \
        opportunity_fingerprint("topic", base, project="quizey")


def test_enqueue_is_idempotent_and_never_resets_lifecycle(store):
    first = _enqueue(store, "topic-a")
    assert first.status is OpportunityStatus.QUEUED
    assert first.attempts == 0

    run = store.start_run("branding")
    store.finish_run(run.run_id, "DO_NOT_PUBLISH")
    claimed = store.claim_opportunities(run.run_id, 2)
    assert [c.opportunity_id for c in claimed] == [first.opportunity_id]

    # Re-discovering the same opportunity returns the claimed row untouched.
    again = _enqueue(store, "topic-a")
    assert again.opportunity_id == first.opportunity_id
    assert again.status is OpportunityStatus.CLAIMED
    assert store.count_backlog() == 0


def test_enqueue_rejects_empty_identity(store):
    with pytest.raises(ValueError):
        store.enqueue_opportunity("", "topic", [_evidence()])
    with pytest.raises(ValueError):
        store.enqueue_opportunity("fp", "  ", [_evidence()])


def test_materially_different_evidence_coexists(store):
    first = _enqueue(store, "topic-a", digests=("hash1",))
    second = _enqueue(store, "topic-a", digests=("hash2",))
    assert first.opportunity_id != second.opportunity_id
    assert first.fingerprint != second.fingerprint
    assert store.count_backlog() == 2


# -------------------------------------------------------------- ordering ---

def test_backlog_orders_fewest_attempts_then_oldest(store):
    older = _enqueue(store, "older")
    newer = _enqueue(store, "newer")
    assert [o.topic for o in store.list_backlog()] == ["older", "newer"]

    store.record_opportunity_decision(
        older.opportunity_id, OpportunityDecision.DEFERRED.value,
        attempts_increment=1)
    assert [o.topic for o in store.list_backlog()] == ["newer", "older"]

    # A failed (retryably) row stays actionable in the same order.
    store.record_opportunity_decision(
        newer.opportunity_id, OpportunityDecision.PUBLISH_FAILED.value,
        attempts_increment=1)
    assert {o.topic for o in store.list_backlog()} == {"older", "newer"}
    assert store.count_backlog() == 2


# ---------------------------------------------------------------- claims ---

def test_claim_takes_up_to_the_limit_oldest_first(store):
    for topic in ("a", "b", "c"):
        _enqueue(store, topic)
    run = store.start_run("branding")
    claimed = store.claim_opportunities(run.run_id, 2)
    assert [c.topic for c in claimed] == ["a", "b"]
    assert all(c.status is OpportunityStatus.CLAIMED for c in claimed)
    assert all(c.claimed_by_run == run.run_id for c in claimed)
    assert [o.topic for o in store.list_backlog()] == ["c"]


def test_claim_rejects_a_non_positive_limit(store):
    run = store.start_run("branding")
    with pytest.raises(ValueError):
        store.claim_opportunities(run.run_id, 0)


def test_two_overlapping_handles_cannot_claim_the_same_row(tmp_path):
    first = StateStore(tmp_path / "shared.db")
    second = StateStore(tmp_path / "shared.db")
    try:
        for topic in ("a", "b", "c"):
            fingerprint = opportunity_fingerprint(
                topic, [("evidence/%s.md" % topic, "hash")])
            first.enqueue_opportunity(
                fingerprint, topic, [_evidence(source="s", digest="hash")])
        run_a = first.start_run("branding")
        run_b = second.start_run("branding")
        claimed_a = {c.opportunity_id
                     for c in first.claim_opportunities(run_a.run_id, 2)}
        claimed_b = {c.opportunity_id
                     for c in second.claim_opportunities(run_b.run_id, 2)}
        assert len(claimed_a) == 2
        assert len(claimed_b) == 1
        assert claimed_a.isdisjoint(claimed_b)
        # All three rows are now claimed; nothing actionable remains.
        assert second.list_backlog(limit=10) == []
    finally:
        first.close()
        second.close()


def test_release_requires_ownership(store):
    row = _enqueue(store, "topic-a")
    run = store.start_run("branding")
    other = store.start_run("branding")
    store.claim_opportunities(run.run_id, 2)
    with pytest.raises(StateConstraintError):
        store.record_opportunity_decision(
            row.opportunity_id, OpportunityDecision.DEFERRED.value,
            release_claim=True, run_id=other.run_id)
    released = store.record_opportunity_decision(
        row.opportunity_id, OpportunityDecision.DEFERRED.value,
        release_claim=True, run_id=run.run_id,
        attempts_increment=1, error="not this time")
    assert released.status is OpportunityStatus.QUEUED
    assert released.attempts == 1
    assert released.last_decision == OpportunityDecision.DEFERRED.value
    assert released.claimed_by_run is None


def test_finalize_accepts_only_resolutions_and_resolves_once(store):
    row = _enqueue(store, "topic-a")
    run = store.start_run("branding")
    store.claim_opportunities(run.run_id, 2)
    with pytest.raises(ValueError):
        store.finalize_opportunity(
            row.opportunity_id, OpportunityStatus.QUEUED, run_id=run.run_id)
    done = store.finalize_opportunity(
        row.opportunity_id, OpportunityStatus.PUBLISHED, run_id=run.run_id,
        publication_id=None, decision=OpportunityDecision.PUBLISHED.value)
    assert done.status is OpportunityStatus.PUBLISHED
    assert done.terminal and not done.actionable
    with pytest.raises(StateConstraintError):
        store.finalize_opportunity(
            row.opportunity_id, OpportunityStatus.REJECTED,
            run_id=run.run_id)
    assert store.count_backlog() == 0


def test_finalize_refuses_another_runs_claim(store):
    row = _enqueue(store, "topic-a")
    run = store.start_run("branding")
    other = store.start_run("branding")
    store.claim_opportunities(run.run_id, 2)
    with pytest.raises(StateConstraintError):
        store.finalize_opportunity(
            row.opportunity_id, OpportunityStatus.REJECTED,
            run_id=other.run_id)


# --------------------------------------------------------------- recovery ---

def _finish(run_id_holder, store, outcome="DO_NOT_PUBLISH"):
    run = store.start_run("branding")
    store.finish_run(run.run_id, outcome)
    run_id_holder.append(run.run_id)
    return run


def test_stale_claims_of_finished_runs_are_released(store):
    row = _enqueue(store, "topic-a")
    holder: list = []
    crashed = _finish(holder, store)
    store.claim_opportunities(crashed.run_id, 2)

    live = store.start_run("branding")
    recovered = store.recover_stale_claims(live.run_id)
    assert [r.opportunity_id for r in recovered] == [row.opportunity_id]
    assert recovered[0].status is OpportunityStatus.QUEUED
    assert recovered[0].last_decision == OpportunityDecision.RECOVERED.value


def test_claims_of_unfinished_runs_are_left_untouched(store):
    row = _enqueue(store, "topic-a")
    live_owner = store.start_run("branding")  # never finished: still live
    store.claim_opportunities(live_owner.run_id, 2)
    live = store.start_run("branding")
    assert store.recover_stale_claims(live.run_id) == []
    assert store.get_opportunity(row.opportunity_id).status is \
        OpportunityStatus.CLAIMED


def test_stale_claim_with_a_published_intent_finalizes_published(store):
    row = _enqueue(store, "topic-a")
    holder: list = []
    crashed = _finish(holder, store)
    store.claim_opportunities(crashed.run_id, 2)
    intent = store.create_publish_intent(
        crashed.run_id, "the post", opportunity_id=row.opportunity_id,
        max_per_run=2)
    store.mark_attempt_started(intent.intent_id)
    publication = store.record_publication(
        intent.intent_id, "published", linkedin_post_id="urn:li:share:1")

    live = store.start_run("branding")
    recovered = store.recover_stale_claims(live.run_id)
    assert recovered[0].status is OpportunityStatus.PUBLISHED
    assert recovered[0].publication_id == publication.publication_id
    # And it can never be republished from the backlog.
    assert store.count_backlog() == 0


def test_stale_claim_with_an_ambiguous_intent_is_blocked(store):
    row = _enqueue(store, "topic-a")
    crashed = _finish([], store, outcome="REQUIRES_HUMAN_INTERVENTION")
    store.claim_opportunities(crashed.run_id, 2)
    intent = store.create_publish_intent(
        crashed.run_id, "the post", opportunity_id=row.opportunity_id,
        max_per_run=2)
    store.mark_attempt_started(intent.intent_id)
    store.record_publication(intent.intent_id, "unknown_requires_review")

    live = store.start_run("branding")
    recovered = store.recover_stale_claims(live.run_id)
    assert recovered[0].status is OpportunityStatus.REQUIRES_REVIEW
    assert store.count_backlog() == 0


def test_stale_claim_with_a_failed_intent_returns_as_retryable(store):
    row = _enqueue(store, "topic-a")
    crashed = _finish([], store, outcome="WORKFLOW_FAILED")
    store.claim_opportunities(crashed.run_id, 2)
    intent = store.create_publish_intent(
        crashed.run_id, "the post", opportunity_id=row.opportunity_id,
        max_per_run=2)
    store.mark_attempt_started(intent.intent_id)
    store.record_publication(intent.intent_id, "failed")

    live = store.start_run("branding")
    recovered = store.recover_stale_claims(live.run_id)
    assert recovered[0].status is OpportunityStatus.QUEUED
    assert recovered[0].attempts == 1
    assert store.count_backlog() == 1


def test_recovery_is_idempotent(store):
    _enqueue(store, "topic-a")
    crashed = _finish([], store)
    store.claim_opportunities(crashed.run_id, 2)
    live = store.start_run("branding")
    assert len(store.recover_stale_claims(live.run_id)) == 1
    assert store.recover_stale_claims(live.run_id) == []


# ------------------------------------------------------------ run limit ---

def test_intents_carry_the_opportunity_link_and_count_per_run(store):
    row = _enqueue(store, "topic-a")
    run = store.start_run("branding")
    intent = store.create_publish_intent(
        run.run_id, "post one", opportunity_id=row.opportunity_id,
        max_per_run=2)
    assert intent.opportunity_id == row.opportunity_id
    assert store.count_intents_for_run(run.run_id) == 1
    assert [i.intent_id for i in store.list_intents_for_run(run.run_id)] == \
        [intent.intent_id]
    legacy = store.create_publish_intent(run.run_id, "post two")
    assert legacy.opportunity_id is None


def test_application_check_and_trigger_each_enforce_two_per_run(store):
    from app.errors import StateConstraintError as Constraint

    run = store.start_run("branding")
    store.create_publish_intent(run.run_id, "one", max_per_run=2)
    store.create_publish_intent(run.run_id, "two", max_per_run=2)
    with pytest.raises(Constraint):
        store.create_publish_intent(run.run_id, "three", max_per_run=2)
    other = store.start_run("branding")
    # The limit is per run, not per system — and legacy rows without the
    # application check are still stopped by the trigger.
    store.create_publish_intent(other.run_id, "other one")
    store.create_publish_intent(other.run_id, "other two")
    with pytest.raises(Constraint):
        store.create_publish_intent(other.run_id, "other three")


def test_unknown_opportunity_is_refused(store):
    with pytest.raises(StateStoreError):
        store.record_opportunity_decision(
            "opp_missing", OpportunityDecision.DEFERRED.value,
            release_claim=True, run_id="branding-x")
    with pytest.raises(StateStoreError):
        store.finalize_opportunity(
            "opp_missing", OpportunityStatus.REJECTED)


# -------------------------------------------------------- discovery I/O ---

class _Section:
    def __init__(self, name, items):
        self.name = name
        self.items = items


class _Item:
    def __init__(self, source, chunk_id, content, evidence_state="DOCUMENTED",
                 category="evidence"):
        self.source = source
        self.chunk_id = chunk_id
        self.content = content
        self.evidence_state = evidence_state
        self.category = category
        self.document_type = None
        self.metadata = {"content_hash": chunk_id.split(":")[0],
                         "category": category}


class _Context:
    def __init__(self, sections):
        self.evidence_sections = sections


def test_persist_discovers_one_row_per_section_idempotently(store):
    context = _Context([
        _Section("certificates", [_Item("evidence/a.md", "h1:0", "A")]),
        _Section("projects", [_Item("evidence/b.md", "h2:0", "B"),
                              _Item("evidence/c.md", "h3:1", "C")]),
    ])
    first = persist_discoveries(store, context)
    assert sorted(o.topic for o in first) == ["certificates", "projects"]
    assert all(o.status is OpportunityStatus.QUEUED for o in first)
    second = persist_discoveries(store, context)
    assert [o.opportunity_id for o in second] == \
        [o.opportunity_id for o in first]
    assert store.count_backlog() == 2


def test_persist_skips_what_cannot_become_a_post(store):
    assert persist_discoveries(store, object()) == []
    assert persist_discoveries(store, _Context([])) == []
    # No citable provenance (empty source/hash) is not persisted.
    context = _Context([_Section("thin", [_Item("", "", "words")])])
    assert persist_discoveries(store, context) == []
    assert store.count_backlog() == 0


def test_snapshot_carries_what_reasoning_needs():
    item = _Item("evidence/a.md", "h1:0", "substance",
                 evidence_state="VERIFIED")
    snap = evidence_snapshot(item)
    assert snap == {
        "source": "evidence/a.md",
        "chunk_id": "h1:0",
        "content_hash": "h1",
        "evidence_state": "VERIFIED",
        "category": "evidence",
        "document_type": None,
        "content": "substance",
    }


def test_reconstructed_context_satisfies_the_agent_contract(store):
    from app.agent.prompt import evidence_options, topic_candidates

    persisted = persist_discoveries(store, _Context([
        _Section("projects", [_Item("evidence/b.md", "h2:0", "B")]),
    ]))
    rebuilt = build_opportunity_context(persisted[0])
    assert not rebuilt.is_insufficient
    assert [t.name for t in topic_candidates(rebuilt)] == ["projects"]
    assert [o.label for o in evidence_options(rebuilt)] == ["E1"]
    assert rebuilt.guidance_sections == ()
