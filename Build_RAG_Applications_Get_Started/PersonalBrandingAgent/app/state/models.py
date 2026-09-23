"""Typed row models for the operational state store, plus time helpers.

Each class mirrors one table and is read back through ``from_row``, so
callers never touch a raw ``sqlite3.Row`` and a column rename fails loudly
in one place instead of silently in a workflow.

Timestamps
    Every timestamp is a UTC ISO-8601 string produced by :func:`utc_now_iso`,
    always with microseconds and a ``+00:00`` offset. That fixed shape is
    what makes lexicographic comparison in SQL agree with chronological
    order, which the stale-lock check relies on. SQLite's own ``datetime()``
    is never used — it emits a different format and would break comparison.
"""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.state.enums import (
    CredentialDerivation,
    DeliveryState,
    LifecycleState,
    PublishState,
    RunOutcome,
    SyncOutcome,
)


def utc_now() -> datetime:
    """The current time, timezone-aware and in UTC."""
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    """Render an aware datetime as the store's canonical UTC timestamp."""
    if moment.tzinfo is None:
        raise ValueError("refusing to store a naive datetime; timestamps are UTC")
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def utc_now_iso() -> str:
    """The current UTC time in the store's canonical format."""
    return to_iso(utc_now())


def iso_in(seconds: float) -> str:
    """A UTC timestamp ``seconds`` from now (used for lock expiry)."""
    return to_iso(utc_now() + timedelta(seconds=seconds))


@dataclass(frozen=True)
class WorkflowRun:
    """One execution of one workflow."""

    run_id: str
    workflow: str
    started_at: str
    finished_at: str | None = None
    outcome: RunOutcome | None = None
    failed_phase: str | None = None
    no_publish_reason: str | None = None
    """Why a DO_NOT_PUBLISH run published nothing (a NoPublishReason value).
    Unconstrained prose to this layer — the vocabulary belongs to the agent —
    and NULL for runs that published, failed, or predate the column."""

    @property
    def finished(self) -> bool:
        """True once the run has been resolved to an outcome."""
        return self.outcome is not None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkflowRun":
        raw = row["outcome"]
        return cls(
            run_id=row["run_id"],
            workflow=row["workflow"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            outcome=RunOutcome(raw) if raw is not None else None,
            failed_phase=row["failed_phase"],
            no_publish_reason=row["no_publish_reason"],
        )


@dataclass(frozen=True)
class SyncCheckpoint:
    """How far a source has been successfully synchronized.

    ``last_revision`` and ``last_synced_at`` advance **only** after a fully
    successful sync. ``last_outcome`` describes the most recent *attempt*,
    which may have failed — in that case the revision is deliberately left
    where it was so the next run re-processes the same range.
    """

    source_name: str
    last_outcome: SyncOutcome
    last_attempt_at: str
    updated_at: str
    last_revision: str | None = None
    last_synced_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SyncCheckpoint":
        return cls(
            source_name=row["source_name"],
            last_outcome=SyncOutcome(row["last_outcome"]),
            last_attempt_at=row["last_attempt_at"],
            updated_at=row["updated_at"],
            last_revision=row["last_revision"],
            last_synced_at=row["last_synced_at"],
        )


@dataclass(frozen=True)
class SourceLifecycleState:
    """The persisted lifecycle of a registered source."""

    source_name: str
    lifecycle: LifecycleState
    updated_at: str
    note: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SourceLifecycleState":
        return cls(
            source_name=row["source_name"],
            lifecycle=LifecycleState(row["lifecycle"]),
            updated_at=row["updated_at"],
            note=row["note"],
        )


@dataclass(frozen=True)
class SchedulePolicy:
    """One workflow's persisted schedule expectation.

    The intervals mirror the cron triggers (branding every 8h, sync daily);
    persisting them here — rather than parsing cron — is what makes a missed
    tick detectable from state alone. ``grace_seconds`` absorbs trigger skew
    and long runs; a tick older than ``expire_after_seconds`` is recorded as
    lapsed rather than still owed.
    """

    workflow: str
    interval_seconds: int
    grace_seconds: int
    expire_after_seconds: int
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SchedulePolicy":
        return cls(
            workflow=row["workflow"],
            interval_seconds=row["interval_seconds"],
            grace_seconds=row["grace_seconds"],
            expire_after_seconds=row["expire_after_seconds"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class MissedWindow:
    """One scheduled tick with no run behind it, and what was decided.

    ``eligible`` — the window is recent; the current run covers it.
    ``expired`` — the window lapsed; the current run proceeds fresh and no
    catch-up publication is owed (none exists by construction).
    ``needs_review`` — a publication ambiguity is unresolved, so no publish
    may go out until a person confirms; the existing pre-publish guard
    enforces that, this row records why.
    """

    window_id: str
    workflow: str
    expected_at: str
    detected_at: str
    determination: str
    covering_run_id: str | None = None
    note: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MissedWindow":
        return cls(
            window_id=row["window_id"],
            workflow=row["workflow"],
            expected_at=row["expected_at"],
            detected_at=row["detected_at"],
            determination=row["determination"],
            covering_run_id=row["covering_run_id"],
            note=row["note"],
        )


@dataclass(frozen=True)
class PublishIntent:
    """A write-ahead record of an intent to publish.

    Written *before* the LinkedIn call. With no read-back from LinkedIn
    (§5.1), this row is the only duplicate protection and the only evidence
    that an attempt may exist.
    """

    intent_id: str
    run_id: str
    state: PublishState
    content: str
    content_hash: str
    created_at: str
    updated_at: str
    topic: str | None = None
    angle: str | None = None
    project: str | None = None
    """The piece of work the post is about, as the caller named it.

    Stored rather than derived: *"have I overused this project?"* is a question
    about what the system has already said, and no content hash or source path
    answers it without guessing which directory a path "belongs" to
    (``PLAN.md`` Step 6, duplicate checks).
    """

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PublishIntent":
        return cls(
            intent_id=row["intent_id"],
            run_id=row["run_id"],
            state=PublishState(row["state"]),
            content=row["content"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            topic=row["topic"],
            angle=row["angle"],
            project=row["project"],
        )


@dataclass(frozen=True)
class EvidenceRef:
    """One piece of knowledge a publication was grounded in.

    The hash is stored alongside the path because the corpus is resynchronized
    every 24 hours: without it, a later audit cannot tell "grounded in
    evidence that has since changed" from "never grounded" (§6, Step 6).
    """

    source_path: str
    content_hash: str


@dataclass(frozen=True)
class Publication:
    """The resolution of a publish intent — what actually happened to it.

    ``outcome == PUBLISHED`` is the authoritative publication history; the
    other two outcomes record that an attempt did not (or may not) have
    produced a post. ``linkedin_post_id`` is present exactly when the outcome
    is ``PUBLISHED``: LinkedIn's response without a post id is treated as a
    failure or an ambiguity, never as success.
    """

    publication_id: str
    intent_id: str
    run_id: str
    outcome: PublishState
    content_hash: str
    recorded_at: str
    linkedin_post_id: str | None = None
    evidence: list[EvidenceRef] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: sqlite3.Row,
                 evidence: list[EvidenceRef] | None = None) -> "Publication":
        return cls(
            publication_id=row["publication_id"],
            intent_id=row["intent_id"],
            run_id=row["run_id"],
            outcome=PublishState(row["outcome"]),
            content_hash=row["content_hash"],
            recorded_at=row["recorded_at"],
            linkedin_post_id=row["linkedin_post_id"],
            evidence=list(evidence or []),
        )


@dataclass(frozen=True)
class PublicationRecord:
    """A publication together with the intent it resolved.

    :class:`Publication` answers *what happened*; this answers *what was sent*
    — the topic, angle and project the intent carried, which live on the intent
    and are what the publishing-history queries are actually about
    (``PLAN.md`` Step 6: the history service must answer "which topics did I
    use?" from stored state, not by inferring it).

    The published *text* is deliberately absent. History reports what was
    published and what it was grounded in; handing generated prose back to the
    Agent is the loop §6.1 exists to prevent, and a caller that genuinely needs
    the text can read it from the intent, which is where it is authoritative.
    """

    publication_id: str
    intent_id: str
    run_id: str
    outcome: PublishState
    content_hash: str
    recorded_at: str
    linkedin_post_id: str | None = None
    topic: str | None = None
    angle: str | None = None
    project: str | None = None
    embedding: bytes | None = None
    """The stored vector of the published text, or ``None`` when none was
    recorded. Opaque bytes: decoding is the publishing layer's business."""

    evidence: tuple[EvidenceRef, ...] = ()

    @property
    def published(self) -> bool:
        """True only for a confirmed publication — the authoritative history."""
        return self.outcome is PublishState.PUBLISHED

    @classmethod
    def from_row(cls, row: sqlite3.Row, evidence: Iterable[EvidenceRef] = ()
    ) -> "PublicationRecord":
        return cls(
            publication_id=row["publication_id"],
            intent_id=row["intent_id"],
            run_id=row["run_id"],
            outcome=PublishState(row["outcome"]),
            content_hash=row["content_hash"],
            recorded_at=row["recorded_at"],
            linkedin_post_id=row["linkedin_post_id"],
            topic=row["topic"],
            angle=row["angle"],
            project=row["project"],
            embedding=row["embedding"],
            evidence=tuple(evidence),
        )


@dataclass(frozen=True)
class OperationalFailure:
    """A structured failure record — an error a workflow can act on.

    ``dedupe_key`` groups repeated identical failures so notifications can be
    rate-limited; ``occurrence_count`` records how many times it has been
    seen. The first occurrence always creates a row and is therefore never
    suppressed (Step 7).
    """

    failure_id: str
    phase: str
    error_category: str
    message: str
    retryable: bool
    requires_human_intervention: bool
    occurrence_count: int
    first_seen_at: str
    last_seen_at: str
    run_id: str | None = None
    workflow: str | None = None
    dedupe_key: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "OperationalFailure":
        return cls(
            failure_id=row["failure_id"],
            phase=row["phase"],
            error_category=row["error_category"],
            message=row["message"],
            retryable=bool(row["retryable"]),
            requires_human_intervention=bool(row["requires_human_intervention"]),
            occurrence_count=row["occurrence_count"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            run_id=row["run_id"],
            workflow=row["workflow"],
            dedupe_key=row["dedupe_key"],
        )


@dataclass(frozen=True)
class Notification:
    """A delivery record for one notification attempt.

    The message body is deliberately **not** stored: everything an operator
    needs is already on the referenced failure, and not persisting the body
    means a secret cannot be written into the store through this table.
    """

    notification_id: str
    recipient: str
    subject: str
    transport: str
    delivery_state: DeliveryState
    created_at: str
    failure_id: str | None = None
    run_id: str | None = None
    smtp_config: str | None = None
    error_message: str | None = None
    attempted_at: str | None = None
    delivered_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Notification":
        return cls(
            notification_id=row["notification_id"],
            recipient=row["recipient"],
            subject=row["subject"],
            transport=row["transport"],
            delivery_state=DeliveryState(row["delivery_state"]),
            created_at=row["created_at"],
            failure_id=row["failure_id"],
            run_id=row["run_id"],
            smtp_config=row["smtp_config"],
            error_message=row["error_message"],
            attempted_at=row["attempted_at"],
            delivered_at=row["delivered_at"],
        )


@dataclass(frozen=True)
class CredentialExpiry:
    """When a stored credential expires, and how that was determined.

    Not a credential and never a token: what is recorded is the *expiry*, the
    issuance time it was derived from, and which evidence produced it. The
    token itself stays on disk in the gitignored file the OAuth flow wrote —
    operational state is not a secret store (``PLAN.md`` Step 5).

    ``source_mtime`` is the modification time of the credential file the
    values were derived from. A run that finds a different mtime knows the
    credential was re-issued and re-derives, so a stale row can never keep a
    dead token looking alive.
    """

    credential: str
    expires_at: str
    derived_from: CredentialDerivation
    source_mtime: str
    recorded_at: str
    updated_at: str
    issued_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CredentialExpiry":
        return cls(
            credential=row["credential"],
            expires_at=row["expires_at"],
            derived_from=CredentialDerivation(row["derived_from"]),
            source_mtime=row["source_mtime"],
            recorded_at=row["recorded_at"],
            updated_at=row["updated_at"],
            issued_at=row["issued_at"],
        )


@dataclass(frozen=True)
class Lock:
    """One held lock. ``expires_at`` is what makes a stale lock detectable."""

    lock_name: str
    owner: str
    acquired_at: str
    heartbeat_at: str
    expires_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Lock":
        return cls(
            lock_name=row["lock_name"],
            owner=row["owner"],
            acquired_at=row["acquired_at"],
            heartbeat_at=row["heartbeat_at"],
            expires_at=row["expires_at"],
        )


@dataclass(frozen=True)
class LockAcquisition:
    """The result of trying to take a lock.

    ``recovered_stale`` distinguishes "the lock was free" from "the lock was
    held by a process that is gone" — the second is a recovery, and must be
    recorded rather than passed over silently (Step 12).
    """

    acquired: bool
    recovered_stale: bool = False
    lock: Lock | None = None
    holder: str | None = None


@dataclass(frozen=True)
class WorkflowPhase:
    """One recorded phase transition of one workflow run.

    Written by the Step 11 orchestration layer: every phase a run enters
    leaves a row, whether it succeeded or failed, so "what did this run do?"
    is answerable by a query. A failing phase additionally leaves an
    ``OperationalFailure`` row and names itself on the run's ``failed_phase``;
    this table is the complete trail, that row is the alert.
    """

    phase_id: str
    run_id: str
    phase: str
    started_at: str
    outcome: str
    finished_at: str | None = None
    error: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkflowPhase":
        return cls(
            phase_id=row["phase_id"],
            run_id=row["run_id"],
            phase=row["phase"],
            started_at=row["started_at"],
            outcome=row["outcome"],
            finished_at=row["finished_at"],
            error=row["error"],
        )
