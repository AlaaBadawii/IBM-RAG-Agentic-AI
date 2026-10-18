"""Publication engagement metrics: the store and the age-comparable baseline.

Metrics are a hand-imported report (there is no live call), read by a person
and never by the pipeline. These tests pin the store contract — a required
non-negative age, repeated readings kept apart, an honest baseline that
compares only comparable ages — and never touch the production database.
"""
import pytest

from app.state import StateStore
from app.state.schema import SCHEMA_VERSION
from app.state.store import StateConstraintError


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "metrics.db") as state:
        yield state


def _publication(store, post_id="urn:li:share:1"):
    run = store.start_run("branding")
    intent = store.create_publish_intent(run.run_id, f"post {post_id}")
    return store.record_publication(
        intent.intent_id, "published", linkedin_post_id=post_id)


def test_schema_is_at_v12_with_the_metrics_table(store):
    assert SCHEMA_VERSION == 13
    assert store.schema_version == 13
    tables = {
        row[0] for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "publication_metrics" in tables


def test_a_recorded_metric_reads_back_with_its_engagement_derived(store):
    publication = _publication(store)

    metric = store.record_publication_metric(
        publication.publication_id, age_hours=6, impressions=1000,
        reactions=10, comments=4, reposts=1)

    stored = store.get_publication_metric(metric.metric_id)
    assert stored is not None
    assert stored.publication_id == publication.publication_id
    assert stored.age_hours == 6
    assert stored.impressions == 1000
    assert stored.engagements == 15
    assert stored.engagement_rate == pytest.approx(0.015)


def test_an_engagement_rate_with_no_impressions_is_zero(store):
    publication = _publication(store)

    metric = store.record_publication_metric(
        publication.publication_id, age_hours=0, impressions=0, reactions=7)

    assert metric.engagements == 7
    assert metric.engagement_rate == 0.0


def test_a_negative_age_or_count_is_refused(store):
    publication = _publication(store)

    with pytest.raises(ValueError):
        store.record_publication_metric(
            publication.publication_id, age_hours=-1)
    with pytest.raises(ValueError):
        store.record_publication_metric(
            publication.publication_id, age_hours=1, impressions=-5)


def test_a_metric_for_an_unknown_publication_is_refused(store):
    with pytest.raises(StateConstraintError):
        store.record_publication_metric("pub_does_not_exist", age_hours=1)


def test_repeated_readings_of_one_post_are_kept_apart(store):
    publication = _publication(store)
    store.record_publication_metric(
        publication.publication_id, age_hours=6, impressions=100)
    store.record_publication_metric(
        publication.publication_id, age_hours=168, impressions=900)

    metrics = store.list_publication_metrics(publication.publication_id)

    assert [m.age_hours for m in metrics] == [168.0, 6.0]


def test_metrics_can_be_listed_for_one_publication(store):
    first = _publication(store, "urn:li:share:1")
    second = _publication(store, "urn:li:share:2")
    store.record_publication_metric(first.publication_id, age_hours=6,
                                    impressions=100)
    store.record_publication_metric(second.publication_id, age_hours=6,
                                    impressions=200)

    only_first = store.list_publication_metrics(first.publication_id)

    assert len(only_first) == 1
    assert only_first[0].publication_id == first.publication_id


def test_the_baseline_counts_only_comparable_ages(store):
    a = _publication(store, "urn:li:share:a")
    b = _publication(store, "urn:li:share:b")
    c = _publication(store, "urn:li:share:c")
    store.record_publication_metric(a.publication_id, age_hours=6,
                                    impressions=1000, reactions=10)
    store.record_publication_metric(b.publication_id, age_hours=7,
                                    impressions=2000, reactions=30)
    # Far outside the tolerance: not comparable, must not move the average.
    store.record_publication_metric(c.publication_id, age_hours=1000,
                                    impressions=999999)

    baseline = store.comparable_age_baseline(6, tolerance_hours=6)

    assert baseline["count"] == 2
    assert baseline["avg_impressions"] == pytest.approx(1500)
    assert baseline["avg_engagements"] == pytest.approx(20)
    assert baseline["avg_engagement_rate"] == pytest.approx(40 / 3000)


def test_the_baseline_can_exclude_a_post_from_its_own_comparison(store):
    a = _publication(store, "urn:li:share:a")
    b = _publication(store, "urn:li:share:b")
    store.record_publication_metric(a.publication_id, age_hours=6,
                                    impressions=1000)
    store.record_publication_metric(b.publication_id, age_hours=6,
                                    impressions=300)

    baseline = store.comparable_age_baseline(
        6, exclude_publication_id=a.publication_id)

    assert baseline["count"] == 1
    assert baseline["avg_impressions"] == pytest.approx(300)


def test_an_empty_baseline_reports_no_average_not_zero(store):
    baseline = store.comparable_age_baseline(6)

    assert baseline["count"] == 0
    assert baseline["avg_impressions"] is None
    assert baseline["avg_engagement_rate"] is None


def test_comparing_a_post_to_its_baseline_reports_the_deltas(store):
    subject = _publication(store, "urn:li:share:subject")
    peer = _publication(store, "urn:li:share:peer")
    store.record_publication_metric(subject.publication_id, age_hours=6,
                                    impressions=1000, reactions=10)
    store.record_publication_metric(peer.publication_id, age_hours=6,
                                    impressions=400, reactions=2)

    comparison = store.compare_publication_to_baseline(subject.publication_id)

    assert comparison["metric"].publication_id == subject.publication_id
    assert comparison["baseline"]["count"] == 1
    assert comparison["impressions_delta"] == pytest.approx(600)
    assert comparison["engagement_rate_delta"] == pytest.approx(0.010 - 0.005)


def test_comparing_a_post_with_no_metric_reports_nothing(store):
    publication = _publication(store)

    comparison = store.compare_publication_to_baseline(publication.publication_id)

    assert comparison == {
        "metric": None, "baseline": None,
        "impressions_delta": None, "engagement_rate_delta": None,
    }
