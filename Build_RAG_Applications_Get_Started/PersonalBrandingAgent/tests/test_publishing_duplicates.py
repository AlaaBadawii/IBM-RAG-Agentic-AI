"""Step 6: the three duplicate checks, and the vectors they need.

``PLAN.md`` Step 6 insists on three *distinct* forms — exact, near, and
overuse — and the tests below are written so that merging them would fail:
each one constructs a case that exactly one of the three can catch.

The embedder is the deterministic fake from ``conftest`` (a token-bucket
vector), so "these two posts are similar" is a reproducible arithmetic fact
rather than a property of a model. Nothing here touches the network.
"""
from datetime import timedelta

import pytest

from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.publishing import (
    DuplicateDetector,
    DuplicateKind,
    DuplicatePolicy,
    PublishRequest,
    PublishingService,
    cosine_similarity,
    evidence_ref,
    pack_embedding,
    unpack_embedding,
)
from app.state.models import to_iso, utc_now

POST_ID = "urn:li:share:7123456789"

#: Eight tokens shared by the "same post, reworded" pair.
BASE = "kaizen throughput regression latency profiling rollout cadence retro"


def publish(store, *, content, topic=None, project=None, evidence=(),
            embedder=None, transport_result=None, now=None, policy=None):
    """Publish one post through the real service, offline."""
    run = store.start_run("branding")
    answer = transport_result or PublicationResult(
        outcome=PublicationOutcome.PUBLISHED,
        message="published",
        api_version="202601",
        attempted_at=to_iso(utc_now()),
        post_id=POST_ID,
    )
    calls: list[str] = []

    def transport(text):
        calls.append(text)
        return answer

    service = PublishingService(store, transport=transport, embedder=embedder,
                               policy=policy)
    report = service.publish(
        PublishRequest(content=content, topic=topic, project=project,
                       evidence=evidence),
        run.run_id,
        now=now,
    )
    return report, calls


def distinct_text(index: int, tokens: int = 8) -> str:
    """Text sharing no token with any other ``distinct_text`` call."""
    return " ".join(f"tok{index}x{position}" for position in range(tokens))


def failed_result() -> PublicationResult:
    return PublicationResult(
        outcome=PublicationOutcome.FAILED,
        message="LinkedIn rejected the post with HTTP 422",
        api_version="202601",
        attempted_at=to_iso(utc_now()),
    )


# --- check 1: exact ----------------------------------------------------------

def test_an_exact_duplicate_is_refused_before_any_request_is_made(state_store):
    """Acceptance: exact duplicates are impossible."""
    text = "A post about the thing I shipped this week."
    first, _ = publish(state_store, content=text)
    assert first.published

    second, calls = publish(state_store, content=text)

    assert second.refused
    assert not calls, "a refused duplicate still reached the transport"
    kinds = [finding.kind for finding in second.duplicates.findings]
    assert kinds == [DuplicateKind.EXACT]
    assert "already published" in second.message


def test_a_refused_duplicate_leaves_no_trace_in_the_run(state_store):
    """Nothing is written for a refusal: there was no attempt to record."""
    text = "A post about the thing I shipped this week."
    publish(state_store, content=text)
    run = state_store.start_run("branding")
    # A transport that would fail the test if it were ever reached.
    service = PublishingService(state_store, transport=lambda _: None)

    report = service.publish(PublishRequest(content=text), run.run_id)

    assert report.refused
    assert state_store.get_intent_for_run(run.run_id) is None
    assert len(state_store.list_publication_records()) == 1


def test_an_unresolved_attempt_blocks_the_same_text(state_store):
    """Exact-duplicate detection cannot prove the words never went out."""
    text = "A post whose outcome nobody knows."
    ambiguous = PublicationResult(
        outcome=PublicationOutcome.UNKNOWN,
        message="read timeout after sending",
        api_version="202601",
        attempted_at=to_iso(utc_now()),
    )
    assert publish(state_store, content=text,
                   transport_result=ambiguous)[0].requires_review

    second, _ = publish(state_store, content=text)

    assert second.refused
    assert second.duplicates.findings[0].kind is DuplicateKind.EXACT


def test_a_rejected_attempt_releases_the_text(state_store):
    """A definitive failure is not a duplicate: the words may be reused."""
    text = "A post LinkedIn rejected outright."
    assert publish(state_store, content=text,
                   transport_result=failed_result())[0].decision.value == "failed"

    second, _ = publish(state_store, content=text)
    assert second.published


# --- check 2: near -----------------------------------------------------------

def test_a_reworded_post_is_caught_by_the_near_duplicate_check(
        state_store, fake_embeddings):
    """Acceptance: near duplicates are detectable."""
    publish(state_store, content=BASE, embedder=fake_embeddings)

    reworded = BASE + " shipping"
    second, calls = publish(state_store, content=reworded,
                            embedder=fake_embeddings)

    assert second.refused
    assert not calls
    finding = second.duplicates.findings[0]
    assert finding.kind is DuplicateKind.NEAR
    assert finding.similarity is not None and finding.similarity >= 0.9
    assert "reworded" in finding.detail


def test_the_near_duplicate_check_reports_what_it_compared(
        state_store, fake_embeddings):
    """"Nothing matched" and "nothing was compared" must not look alike."""
    publish(state_store, content=BASE, embedder=fake_embeddings)

    # Same length, no shared vocabulary: a different post about a different thing.
    unrelated = " ".join(f"{token}q" for token in BASE.split())
    report, calls = publish(state_store, content=unrelated,
                            embedder=fake_embeddings)

    assert report.published, "an unrelated post was refused as a duplicate"
    assert calls
    assert report.duplicates.compared_publications == 1
    assert report.duplicates.findings == ()
    assert report.duplicates.unchecked == ()


def test_a_post_stored_without_a_vector_is_not_compared(
        state_store, fake_embeddings):
    """No vector is not the same fact as no similarity."""
    publish(state_store, content=BASE)  # no embedder configured
    detector = DuplicateDetector(state_store, embedder=fake_embeddings)

    report = detector.check(PublishRequest(content=BASE + " shipping"))

    assert report.compared_publications == 0
    assert report.findings == ()
    assert not report.must_not_publish


def test_near_duplicate_detection_is_not_claimed_without_an_embedder(state_store):
    publish(state_store, content=BASE)
    detector = DuplicateDetector(state_store)

    assert detector.can_detect_near_duplicates is False
    report = detector.check(PublishRequest(content=BASE + " shipping"))
    assert report.compared_publications == 0
    assert report.unchecked == ()


def test_an_embedder_failure_refuses_rather_than_publishing_unchecked(state_store):
    """Fails closed: the required check did not run, so nothing is sent."""
    class BrokenEmbedder:
        def embed_query(self, text):
            raise RuntimeError("the embedding provider is unavailable")

    first, _ = publish(state_store, content=BASE, embedder=BrokenEmbedder())

    assert first.refused
    assert not first.duplicates.findings
    assert "near-duplicate check could not run" in first.message
    assert "RuntimeError" in first.message
    assert first.duplicates.unchecked


def test_the_threshold_is_policy_not_a_magic_number(state_store, fake_embeddings):
    """A stricter policy refuses what a looser one allows."""
    publish(state_store, content=BASE, embedder=fake_embeddings)
    candidate = BASE + " shipping"

    strict = DuplicateDetector(state_store, embedder=fake_embeddings,
                               policy=DuplicatePolicy(near_duplicate_threshold=0.5))
    loose = DuplicateDetector(state_store, embedder=fake_embeddings,
                              policy=DuplicatePolicy(near_duplicate_threshold=0.999))

    assert strict.check(PublishRequest(content=candidate)).blocked
    assert not loose.check(PublishRequest(content=candidate)).blocked


def test_an_impossible_policy_is_refused_at_construction():
    with pytest.raises(ValueError, match="threshold"):
        DuplicatePolicy(near_duplicate_threshold=0.0)
    with pytest.raises(ValueError, match="positive"):
        DuplicatePolicy(overuse_window_days=0)
    with pytest.raises(ValueError, match="at least 1"):
        DuplicatePolicy(max_topic_uses=0)


# --- check 3: overuse --------------------------------------------------------

def test_topic_overuse_is_detected_from_stored_topics(state_store):
    """Acceptance: topic overuse is detectable."""
    for index in range(3):
        assert publish(state_store, content=distinct_text(index),
                       topic="incremental sync")[0].published

    fourth, calls = publish(state_store, content=distinct_text(9),
                            topic="incremental sync")

    assert fourth.refused
    assert not calls
    kinds = [finding.kind for finding in fourth.duplicates.findings]
    assert kinds == [DuplicateKind.TOPIC_OVERUSE]
    assert fourth.duplicates.findings[0].uses == 3


def test_project_overuse_is_caught_without_any_text_similarity(state_store):
    """The check text similarity cannot make: same project, nothing in common.

    Every post here shares no vocabulary with any other, so a merged
    "similarity" verdict could never produce this refusal — which is precisely
    why ``PLAN.md`` requires three separate checks.
    """
    for index in range(3):
        publish(state_store, content=distinct_text(index),
                topic=f"topic-{index}", project="PersonalBrandingAgent")

    fourth, _ = publish(state_store, content=distinct_text(9), topic="topic-9",
                        project="PersonalBrandingAgent")

    assert fourth.refused
    kinds = [finding.kind for finding in fourth.duplicates.findings]
    assert kinds == [DuplicateKind.PROJECT_OVERUSE]
    assert fourth.duplicates.findings[0].subject == "PersonalBrandingAgent"


def test_evidence_overuse_is_detected_from_stored_references(state_store):
    """Acceptance: overuse is detectable from stored evidence references."""
    ref = evidence_ref("evidence/backend/fastapi.md", "abc123:0")
    for index in range(3):
        publish(state_store, content=distinct_text(index), topic=f"topic-{index}",
                evidence=(ref,))

    fourth, _ = publish(state_store, content=distinct_text(9), topic="topic-9",
                        evidence=(ref,))

    assert fourth.refused
    kinds = [finding.kind for finding in fourth.duplicates.findings]
    assert kinds == [DuplicateKind.EVIDENCE_OVERUSE]
    assert fourth.duplicates.findings[0].subject == "evidence/backend/fastapi.md"
    assert fourth.duplicates.findings[0].uses == 3


def test_evidence_overuse_distinguishes_changed_content(state_store):
    """The same path with different content is different evidence.

    The corpus is resynchronized every 24 hours, so counting by path alone
    would report a source as "overused" when the post would actually be the
    first to cite what is there now.
    """
    changed = evidence_ref("evidence/backend/fastapi.md", "hashA:0")
    current = evidence_ref("evidence/backend/fastapi.md", "hashB:0")
    for index in range(3):
        publish(state_store, content=distinct_text(index), topic=f"topic-{index}",
                evidence=(changed,))

    report, _ = publish(state_store, content=distinct_text(9), topic="topic-9",
                        evidence=(current,))

    assert report.published


def test_overuse_counts_only_published_posts(state_store):
    """A post that never went out is not a repetition."""
    ref = evidence_ref("evidence/backend/fastapi.md", "abc123:0")
    publish(state_store, content=distinct_text(1), topic="sync", evidence=(ref,))
    publish(state_store, content=distinct_text(2), topic="sync", evidence=(ref,))
    publish(state_store, content=distinct_text(3), topic="sync", evidence=(ref,),
            transport_result=failed_result())

    report, _ = publish(state_store, content=distinct_text(4), topic="sync",
                        evidence=(ref,))

    assert report.published, "a failed attempt was counted as a use"


def test_overuse_counts_only_what_is_inside_the_window(state_store):
    """A topic revisited after the window is not repetition."""
    for index in range(3):
        publish(state_store, content=distinct_text(index), topic="sync")

    later = utc_now() + timedelta(days=60)
    report, _ = publish(state_store, content=distinct_text(9), topic="sync",
                        now=later)

    assert report.published
    assert report.duplicates.findings == ()


def test_the_three_checks_are_reported_separately(state_store, fake_embeddings):
    """A report says what it found, and an exact duplicate is the whole answer.

    The first of the three posts is offered again here, at a point where its
    topic and its evidence have both been used three times. The report presents
    the exact-duplicate finding alone: the checks are not blended, and a
    request that could never be sent is not asked to run the others.
    """
    ref = evidence_ref("evidence/backend/fastapi.md", "abc123:0")
    texts = ["A post about incremental synchronization and its cost.",
             "A post about retrieval evaluation and what it showed.",
             "A post about the state store and why it exists."]
    for text in texts:
        publish(state_store, content=text, topic="sync", evidence=(ref,),
                embedder=fake_embeddings)

    report, _ = publish(state_store, content=texts[0], topic="sync",
                        evidence=(ref,), embedder=fake_embeddings)

    kinds = [finding.kind for finding in report.duplicates.findings]
    assert kinds == [DuplicateKind.EXACT]


# --- the vectors the near check compares -------------------------------------

def test_a_stored_vector_round_trips():
    vector = [0.25, -1.5, 3.0, 0.0]
    assert unpack_embedding(pack_embedding(vector)) == pytest.approx(vector)


def test_a_publication_with_no_vector_reads_back_as_nothing():
    assert unpack_embedding(None) is None


def test_a_non_finite_vector_is_refused_before_it_is_stored():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="non-finite"):
            pack_embedding([1.0, bad])
    with pytest.raises(ValueError, match="empty"):
        pack_embedding([])


def test_a_ragged_stored_vector_is_reported_rather_than_guessed():
    with pytest.raises(ValueError, match="whole number"):
        unpack_embedding(b"\x00\x01\x02")


def test_similarity_is_undefined_for_a_vector_with_no_direction():
    """Undefined is not zero: only one of them means "unlike"."""
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) is None
    assert cosine_similarity([1.0], [1.0, 2.0]) is None
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
