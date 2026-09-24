"""M6.1: the verified body is what the publisher sends — byte for byte.

The production failure was LinkedIn receiving a title where the full post
belonged. The trace proved no code path substitutes metadata for content,
so these tests pin that property: through the real
``PublishingService.publish`` with a capturing transport, the exact bytes
the transport receives must equal the verified draft body, even when a
title-like value sits in every metadata field.
"""
from dataclasses import dataclass

import pytest

from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.publishing import (
    PublishingService,
    PublishRequest,
    evidence_ref,
)
from app.state import RunOutcome, StateStore

TITLE = "Meet Abu Prompt"

BODY = (
    "Meet Abu Prompt (@AbuPrompt), an autonomous personal-branding system "
    "built around real engineering work.\n\n"
    "Today it tracks developments, gathers evidence, and verifies claims "
    "before anything is published.\n\n"
    "Planned: mention-triggered responses are future work."
)


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "payload.db") as state:
        yield state


def _capturing_transport(captured, post_id="urn:li:test-post"):
    def transport(text):
        captured.append(text)
        return PublicationResult(
            outcome=PublicationOutcome.PUBLISHED,
            message="published",
            post_id=post_id,
            api_version="202607",
            attempted_at="2026-09-24T00:00:00+00:00",
        )

    return transport


def _request(body=BODY):
    return PublishRequest(
        content=body,
        topic=TITLE,
        angle=TITLE,
        project=TITLE,
        evidence=(evidence_ref("evidence/a.md", "abc123:0"),),
    )


def test_transport_receives_the_verified_body_not_the_title(store):
    """Every metadata field carries the title; the wire must carry the body."""
    captured = []
    service = PublishingService(
        store, transport=_capturing_transport(captured))
    run = store.start_run("branding")

    report = service.publish(_request(), run.run_id)

    assert report.published
    assert captured == [BODY]
    assert captured[0] != TITLE


def test_stored_intent_matches_the_sent_body(store):
    captured = []
    service = PublishingService(
        store, transport=_capturing_transport(captured))
    run = store.start_run("branding")

    report = service.publish(_request(), run.run_id)

    intent = store.get_publish_intent(report.intent_id)
    assert intent is not None
    assert intent.content == BODY
    assert intent.content == captured[0]


def test_preview_matches_what_publish_would_send(store):
    """The preflight shows the exact payload without side effects."""
    captured = []
    refusing = []
    service = PublishingService(
        store, transport=_refusing_transport(refusing))
    run = store.start_run("branding")

    preview = service.preview_publish(_request(), run.run_id)

    assert preview.content == BODY
    assert preview.would_publish is True
    assert captured == [] and refusing == []
    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == 0
    assert store._conn.execute(
        "SELECT COUNT(*) FROM publications").fetchone()[0] == 0


def _refusing_transport(called):
    def transport(text):  # pragma: no cover - must never run
        called.append(text)
        raise AssertionError("preview must not send")

    return transport


def test_preview_reports_refusal_without_writing(store):
    run = store.start_run("branding")
    first = PublishingService(store, transport=_capturing_transport([]))
    first.publish(_request(), run.run_id)
    run2 = store.start_run("branding")
    previewer = PublishingService(store, transport=_refusing_transport([]))

    preview = previewer.preview_publish(_request(), run2.run_id)

    assert preview.would_publish is False
    assert preview.content == BODY


def test_notification_uses_persisted_intent_content(store):
    """The email body comes from the stored intent — the same bytes the
    service sent — not from any in-memory object."""
    from app.notify.models import PublishedPost
    from app.workflows.branding import _report_publication

    captured = []
    service = PublishingService(
        store, transport=_capturing_transport(captured))
    run = store.start_run("branding")
    report = service.publish(_request(), run.run_id)
    assert report.published

    sent = {}

    class _Notifier:
        def notify_publication(self, post: PublishedPost, *, run_id=None):
            sent["content"] = post.content
            sent["post_id"] = post.post_id

    _report_publication(store, _Notifier(), run.run_id,
                        report.linkedin_post_id)

    assert sent["content"] == BODY
    assert sent["content"] == captured[0]
    assert sent["post_id"] == "urn:li:test-post"


def test_published_run_pairs_do_not_publish_with_published(store):
    """Lifecycle triple: agent PUBLISH decision and service PUBLISHED
    outcome terminate the run as DO_NOT_PUBLISH *with* exactly one linked
    PUBLISHED publication — the consistent record, pinned here."""
    from app.workflows.branding import run_branding

    captured = []
    body_holder: dict = {}

    @dataclass
    class _Draft:
        content: str = BODY

    @dataclass
    class _Proposal:
        topic: str = TITLE
        angle: str | None = None
        project: str | None = None
        evidence: tuple = ()

    @dataclass
    class _Result:
        failed: bool = False
        is_publishable: bool = True
        reason: object = None
        proposal: object = None
        draft: object = None

        def __post_init__(self):
            self.proposal = _Proposal()
            self.draft = _Draft()

    class _Agent:
        def run(self, _context):
            return _Result()

    class _Notifier:
        def __init__(self):
            self.posts = []

        def notify_publication(self, post, *, run_id=None):
            self.posts.append(post)

        def notify_run(self, _run_id):
            raise AssertionError("no failure notification on success")

    holder: dict = {}

    def _notifier_factory(_store):
        holder["notifier"] = _Notifier()
        return holder["notifier"]

    from app.workflows.branding import BrandingConfig

    def _publish(agent_result, run_id, prod_store):
        refs = tuple(
            evidence_ref(item.source, item.chunk_id)
            for item in (agent_result.proposal.evidence or ()))
        return PublishingService(
            prod_store, transport=_capturing_transport(captured)).publish(
                PublishRequest(
                    content=agent_result.draft.content,
                    topic=agent_result.proposal.topic,
                    angle=agent_result.proposal.angle,
                    project=agent_result.proposal.project,
                    evidence=refs),
                run_id)

    cfg = BrandingConfig(
        store_factory=lambda: StateStore(store.path),
        assemble_fn=lambda _store: object(),
        agent_factory=lambda _store: _Agent(),
        publish_fn=_publish,
        history_fn=lambda _store: _EmptyHistory(),
        notifier_factory=_notifier_factory,
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert captured == [BODY]
    with StateStore(store.path) as check:
        run = check.get_run(result.run_id)
        assert run.outcome is RunOutcome.DO_NOT_PUBLISH
        pubs = check._conn.execute(
            "SELECT outcome, linkedin_post_id FROM publications "
            "WHERE run_id = ?", (result.run_id,)).fetchall()
        assert [(p[0], p[1]) for p in pubs] == [
            ("published", "urn:li:test-post")]
    assert holder["notifier"].posts[0].content == BODY


class _EmptyHistory:
    def requires_review(self, limit=None):
        return []
