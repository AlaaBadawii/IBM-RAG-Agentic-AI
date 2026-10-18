"""Time-windowed, angle-aware writing constraints (Phase 3, RC-4).

``publishing_constraints`` used to hand the writer a *cumulative* tally of
topics, so "stories_lessons has been covered" blocked an entirely new story in
that category. The constraint is now windowed to the recent past — anchored to
the newest publication, because this layer holds no clock — and the angle is
the first-class signal.

No model, no network, no store: the digest is built by hand.
"""
from app.agent.models import (
    REPETITION_WINDOW_DAYS,
    HistoryDigest,
    publishing_constraints,
)
from app.publishing.models import PublicationSummary, UsageCount


def _pub(published_at, *, angle=None, topic=None, project=None):
    return PublicationSummary(
        publication_id=f"pub-{published_at}",
        run_id="run",
        published_at=published_at,
        content_hash="abc",
        topic=topic,
        angle=angle,
        project=project,
    )


def _usage(value, last_used_at):
    return UsageCount(value=value, uses=3, last_used_at=last_used_at,
                      publication_ids=("pub-1",))


def test_no_publications_means_no_windowing():
    """Backward compatible: a digest with only counts disables the window,
    because there is no anchor to measure "recent" against."""
    digest = HistoryDigest(topics=(_usage("audit", "2020-01-01T00:00:00Z"),))
    constraints = publishing_constraints(digest)
    assert constraints.recent_topics == ("audit",)


def test_query_with_no_publications_is_cumulative_but_windowed_is_opt_in():
    digest = HistoryDigest(topics=(_usage("audit", "2020-01-01T00:00:00Z"),))
    assert publishing_constraints(digest, window_days=None).recent_topics == (
        "audit",)


def test_coverage_older_than_the_window_is_dropped():
    digest = HistoryDigest(
        publications=(_pub("2026-06-01T00:00:00Z"),),
        topics=(
            _usage("stories_lessons", "2026-04-15T00:00:00Z"),  # old
            _usage("projects", "2026-05-28T00:00:00Z"),        # recent
        ),
        projects=(
            _usage("Quizey", "2026-05-29T00:00:00Z"),          # recent
        ),
    )
    constraints = publishing_constraints(digest, window_days=30)

    assert constraints.recent_topics == ("projects",)
    assert constraints.recent_projects == ("Quizey",)


def test_an_old_category_does_not_block_a_new_angle():
    """The incident's core: a stale story category was blocking new stories."""
    digest = HistoryDigest(
        publications=(
            _pub("2026-06-01T00:00:00Z", angle="a CI debugging story"),
            _pub("2026-03-01T00:00:00Z", angle="an ancient lesson"),
        ),
    )
    constraints = publishing_constraints(digest, window_days=30)

    assert constraints.recent_angles == ("a CI debugging story",)
    assert "an ancient lesson" not in constraints.recent_angles


def test_the_window_is_anchored_to_the_newest_publication():
    digest = HistoryDigest(
        publications=(
            _pub("2026-06-01T00:00:00Z", angle="newest"),
            _pub("2026-05-20T00:00:00Z", angle="inside"),
            _pub("2026-04-01T00:00:00Z", angle="outside"),
        ),
    )
    constraints = publishing_constraints(digest, window_days=30)
    assert constraints.recent_angles == ("newest", "inside")


def test_unparseable_timestamps_are_kept_not_dropped():
    digest = HistoryDigest(
        publications=(_pub("2026-06-01T00:00:00Z"),),
        topics=(_usage("mystery", "not-a-timestamp"),),
    )
    constraints = publishing_constraints(digest, window_days=30)
    assert constraints.recent_topics == ("mystery",)


def test_window_days_none_reproduces_cumulative_behavior():
    digest = HistoryDigest(
        publications=(_pub("2026-06-01T00:00:00Z"),),
        topics=(_usage("stories_lessons", "2020-01-01T00:00:00Z"),),
        projects=(_usage("Old", "2020-01-01T00:00:00Z"),),
    )
    constraints = publishing_constraints(digest, window_days=None)
    assert constraints.recent_topics == ("stories_lessons",)
    assert constraints.recent_projects == ("Old",)
    assert REPETITION_WINDOW_DAYS == 30
