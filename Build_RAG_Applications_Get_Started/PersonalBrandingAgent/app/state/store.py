"""Operational state store — the system's durable memory of what it *did*.

This is the lowest layer of the application and depends on nothing above it.
Every later step reads or writes it; it reads nothing but itself.

What belongs here
    Workflow runs, synchronization checkpoints, source lifecycle, publish
    intents, publications and their evidence references, operational
    failures, notification deliveries, and locks. In one sentence: what the
    system has done.

    One row is a fact about the world rather than about the system: the
    expiry of the stored LinkedIn credential (``linkedin_credential_expiry``,
    Step 5). It belongs here because it must outlive the process that derived
    it — a credential that expires between runs has to be detectable by the
    run that comes after — and because there is nowhere else durable.

What must never belong here
    Knowledge about the user. The `data/` corpus and its Chroma index are a
    different store with different authority (``PLAN.md`` §6), and the two are
    never mixed — in particular, a generated post must never become evidence
    about the user, and publishing history is deliberately *not* indexed into
    Chroma (§6.1). This module never imports the retrieval or ingestion
    layers, which is what makes that structurally true rather than merely
    intended.

Design commitments
    * Single SQLite file, created on first use in a gitignored location.
    * Foreign keys and WAL mode, set on every connection.
    * **Correctness lives in constraints, not in callers.** One publish per
      run and one unresolved intent per content hash are database
      guarantees; see ``schema.py`` for the full table.
    * Narrow, typed operations. No SQL is exposed outside this package, and
      every read returns a typed model rather than a ``sqlite3.Row``.
    * All timestamps are UTC strings (see ``models.py``).
    * Writes never fail silently. A refused write raises; a caller can never
      mistake a failed write for a successful one.

Failure policy
    The store **fails closed**. There is no operation here that returns a
    permissive default on error, and no path that lets a publish proceed
    without a durable intent. If the store cannot be opened, the constructor
    raises and no usable object exists; if it is closed or breaks later,
    every operation raises :class:`StateStoreError`.
"""
import sqlite3
import uuid
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TypeVar

from app.errors import StateConstraintError, StateStoreError
from app.paths import STATE_DB_PATH
from app.state.enums import (
    TERMINAL_PUBLISH_STATES,
    CredentialDerivation,
    DeliveryState,
    LifecycleState,
    PublishState,
    RunOutcome,
    SyncOutcome,
    Workflow,
)
from app.state.models import (
    CredentialExpiry,
    EvidenceRef,
    Lock,
    LockAcquisition,
    Notification,
    OperationalFailure,
    Publication,
    PublicationRecord,
    PublishIntent,
    SourceLifecycleState,
    SyncCheckpoint,
    WorkflowRun,
    iso_in,
    utc_now,
    utc_now_iso,
)
from app.state.schema import SCHEMA_VERSION, ensure_schema

#: Default lock lifetime. Step 12 owns the configured value; keeping it here
#: as a default parameter rather than a config key avoids adding configuration
#: that this step does not use.
DEFAULT_LOCK_TTL_SECONDS = 3600.0

#: How long a writer waits for a competing writer before giving up. Bounded on
#: purpose: waiting forever inside an unattended workflow is indistinguishable
#: from hanging.
BUSY_TIMEOUT_SECONDS = 5.0

_EnumT = TypeVar("_EnumT")


def content_hash_of(text: str) -> str:
    """Deterministic hash of post text, used for exact-duplicate detection.

    Distinct from the ingestion layer's content hash by design: that one
    hashes cleaned corpus chunks, this one hashes a candidate post. They are
    not comparable and are never stored in the same column.
    """
    return sha256(text.encode("utf-8")).hexdigest()


def _coerce_enum(value: "_EnumT | str", enum_cls: type[_EnumT], field: str) -> _EnumT:
    """Accept an enum member or its string value; reject anything else.

    Anything outside the vocabulary is a caller bug and is caught here, before
    any SQL is built. The database CHECK constraint remains the backstop for
    writes that bypass this API entirely.
    """
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_cls)  # type: ignore[attr-defined]
        raise ValueError(
            f"{field} must be one of: {allowed} (got {value!r})"
        ) from exc


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _new_run_id(workflow: str) -> str:
    """A run id that is unique and readable in a log or a query."""
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"{workflow}-{stamp}-{uuid.uuid4().hex[:8]}"


class StateStore:
    """Typed access to the operational state database."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else STATE_DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._open()

    # -- lifecycle ---------------------------------------------------------

    @property
    def path(self) -> Path:
        """Location of the store's file."""
        return self._path

    @property
    def schema_version(self) -> int:
        """The schema version this store is at."""
        return SCHEMA_VERSION

    def close(self) -> None:
        """Close the connection. Idempotent; further operations will raise."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _open(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), timeout=BUSY_TIMEOUT_SECONDS)
        except (sqlite3.Error, OSError) as exc:
            raise StateStoreError(
                f"state store unavailable at {self._path}: {exc}"
            ) from exc
        try:
            conn.row_factory = sqlite3.Row
            # Take control of transactions: this module issues its own
            # BEGIN/COMMIT so multi-statement operations are atomic and
            # migrations can be rolled back as a unit.
            conn.isolation_level = None
            conn.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_SECONDS * 1000)}")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA synchronous = NORMAL")
            ensure_schema(conn)
        except StateStoreError:
            conn.close()
            raise
        except sqlite3.Error as exc:
            conn.close()
            raise StateStoreError(
                f"state store unusable at {self._path}: {exc}"
            ) from exc
        self._conn = conn

    # -- plumbing ----------------------------------------------------------

    def _require_open(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StateStoreError(
                f"state store at {self._path} is closed; refusing to operate"
            )
        return self._conn

    def _write(self, sql: str, params: tuple, what: str) -> sqlite3.Cursor:
        conn = self._require_open()
        try:
            return conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise StateConstraintError(
                f"{what} was rejected by a database constraint: {exc}"
            ) from exc
        except sqlite3.Error as exc:
            raise StateStoreError(f"{what} failed: {exc}") from exc

    def _read(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = self._require_open()
        try:
            return conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StateStoreError(f"reading from the state store failed: {exc}") from exc

    @contextmanager
    def _transaction(self, what: str) -> Iterator[sqlite3.Connection]:
        """Run a multi-statement operation atomically."""
        conn = self._require_open()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise StateStoreError(f"{what} could not start: {exc}") from exc
        try:
            yield conn
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass  # the original failure is the one that matters
            raise
        try:
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            raise StateStoreError(f"{what} could not be committed: {exc}") from exc

    # -- workflow runs -----------------------------------------------------

    def start_run(self, workflow: Workflow | str,
                  run_id: str | None = None) -> WorkflowRun:
        """Record the start of a run. Its outcome is unset until it finishes."""
        name = workflow.value if isinstance(workflow, Workflow) else str(workflow)
        if not name.strip():
            raise ValueError("workflow must be a non-empty name")
        new_id = run_id or _new_run_id(name)
        self._write(
            "INSERT INTO workflow_runs (run_id, workflow, started_at) "
            "VALUES (?, ?, ?)",
            (new_id, name, utc_now_iso()),
            f"starting run {new_id}",
        )
        return self.get_run(new_id)  # type: ignore[return-value]

    def finish_run(self, run_id: str, outcome: RunOutcome | str,
                   failed_phase: str | None = None) -> WorkflowRun:
        """Resolve a run to exactly one of the three outcomes.

        This is the only way a run acquires an outcome, so "how did this run
        end?" is answerable by a query and never has to be inferred from a
        log line or an exit code at read time.
        """
        resolved = _coerce_enum(outcome, RunOutcome, "outcome")
        cursor = self._write(
            "UPDATE workflow_runs SET outcome = ?, finished_at = ?, "
            "failed_phase = ? WHERE run_id = ? AND outcome IS NULL",
            (resolved.value, utc_now_iso(), failed_phase, run_id),
            f"finishing run {run_id}",
        )
        if cursor.rowcount == 0:
            raise StateStoreError(
                f"finishing run {run_id} matched no unfinished run "
                f"(unknown run id, or already resolved)"
            )
        return self.get_run(run_id)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> WorkflowRun | None:
        rows = self._read(
            "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
        )
        return WorkflowRun.from_row(rows[0]) if rows else None

    def list_runs(self, workflow: Workflow | str | None = None,
                  limit: int = 50) -> list[WorkflowRun]:
        """Most recent runs first."""
        if workflow is None:
            rows = self._read(
                "SELECT * FROM workflow_runs ORDER BY started_at DESC, "
                "run_id DESC LIMIT ?",
                (limit,),
            )
        else:
            name = workflow.value if isinstance(workflow, Workflow) else str(workflow)
            rows = self._read(
                "SELECT * FROM workflow_runs WHERE workflow = ? "
                "ORDER BY started_at DESC, run_id DESC LIMIT ?",
                (name, limit),
            )
        return [WorkflowRun.from_row(row) for row in rows]

    def list_unfinished_runs(self) -> list[WorkflowRun]:
        """Runs with no outcome — including any interrupted by a crash.

        An unfinished run is not an error in itself; it is how an interrupted
        run is *found* on the next invocation (Step 12).
        """
        rows = self._read(
            "SELECT * FROM workflow_runs WHERE outcome IS NULL "
            "ORDER BY started_at"
        )
        return [WorkflowRun.from_row(row) for row in rows]

    # -- synchronization checkpoints ---------------------------------------

    def get_checkpoint(self, source_name: str) -> SyncCheckpoint | None:
        rows = self._read(
            "SELECT * FROM sync_checkpoints WHERE source_name = ?",
            (source_name,),
        )
        return SyncCheckpoint.from_row(rows[0]) if rows else None

    def list_checkpoints(self) -> list[SyncCheckpoint]:
        rows = self._read(
            "SELECT * FROM sync_checkpoints ORDER BY source_name"
        )
        return [SyncCheckpoint.from_row(row) for row in rows]

    def record_sync_success(self, source_name: str, revision: str) -> SyncCheckpoint:
        """Advance a source's checkpoint. Call only after ingestion succeeds."""
        if not revision:
            raise ValueError("revision must be non-empty")
        now = utc_now_iso()
        self._write(
            "INSERT INTO sync_checkpoints (source_name, last_revision, "
            "last_synced_at, last_attempt_at, last_outcome, updated_at) "
            "VALUES (?, ?, ?, ?, 'SUCCEEDED', ?) "
            "ON CONFLICT (source_name) DO UPDATE SET "
            "last_revision = excluded.last_revision, "
            "last_synced_at = excluded.last_synced_at, "
            "last_attempt_at = excluded.last_attempt_at, "
            "last_outcome = excluded.last_outcome, "
            "updated_at = excluded.updated_at",
            (source_name, revision, now, now, now),
            f"recording a checkpoint for {source_name}",
        )
        return self.get_checkpoint(source_name)  # type: ignore[return-value]

    def record_sync_failure(self, source_name: str) -> SyncCheckpoint:
        """Record a failed attempt **without** advancing the checkpoint.

        The stored revision stays where it was, so the next run re-processes
        the same range; the content-hash layer underneath makes that
        re-processing idempotent.
        """
        now = utc_now_iso()
        self._write(
            "INSERT INTO sync_checkpoints (source_name, last_revision, "
            "last_synced_at, last_attempt_at, last_outcome, updated_at) "
            "VALUES (?, NULL, NULL, ?, 'FAILED', ?) "
            "ON CONFLICT (source_name) DO UPDATE SET "
            "last_attempt_at = excluded.last_attempt_at, "
            "last_outcome = 'FAILED', "
            "updated_at = excluded.updated_at",
            (source_name, now, now),
            f"recording a failed sync for {source_name}",
        )
        return self.get_checkpoint(source_name)  # type: ignore[return-value]

    # -- source lifecycle ---------------------------------------------------

    def get_source_lifecycle(self, source_name: str) -> SourceLifecycleState | None:
        rows = self._read(
            "SELECT * FROM source_lifecycle WHERE source_name = ?",
            (source_name,),
        )
        return SourceLifecycleState.from_row(rows[0]) if rows else None

    def list_source_lifecycles(self) -> list[SourceLifecycleState]:
        rows = self._read(
            "SELECT * FROM source_lifecycle ORDER BY source_name"
        )
        return [SourceLifecycleState.from_row(row) for row in rows]

    def set_source_lifecycle(self, source_name: str,
                             lifecycle: LifecycleState | str,
                             note: str | None = None) -> SourceLifecycleState:
        """Persist an explicit lifecycle. Never derived, never inferred."""
        state = _coerce_enum(lifecycle, LifecycleState, "lifecycle")
        now = utc_now_iso()
        self._write(
            "INSERT INTO source_lifecycle (source_name, lifecycle, note, "
            "updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (source_name) DO UPDATE SET "
            "lifecycle = excluded.lifecycle, note = excluded.note, "
            "updated_at = excluded.updated_at",
            (source_name, state.value, note, now),
            f"setting the lifecycle of {source_name}",
        )
        return self.get_source_lifecycle(source_name)  # type: ignore[return-value]

    # -- publish intents ----------------------------------------------------

    def create_publish_intent(self, run_id: str, content: str,
                              topic: str | None = None,
                              angle: str | None = None,
                              content_hash: str | None = None,
                              project: str | None = None,
                              ) -> PublishIntent:
        """Record the intent to publish, **before** the LinkedIn call.

        With no read-back from LinkedIn, this row is the only duplicate
        protection that exists and the only evidence that an attempt may have
        happened. Two database constraints apply, and both are deliberate:

        * one intent per run — ``MAX_PUBLISHES_PER_RUN = 1``;
        * one *unresolved* intent per content hash, across runs, so the same
          post cannot be sent twice.

        Failing either of them raises :class:`StateConstraintError`. That is
        the intended behavior: the caller must not publish.
        """
        if not content.strip():
            raise ValueError("refusing to record a publish intent for empty content")
        intent_id = _new_id("intent")
        now = utc_now_iso()
        self._write(
            "INSERT INTO publish_intents (intent_id, run_id, state, content, "
            "content_hash, topic, angle, project, created_at, updated_at) "
            "VALUES (?, ?, 'intent_created', ?, ?, ?, ?, ?, ?, ?)",
            (
                intent_id,
                run_id,
                content,
                content_hash or content_hash_of(content),
                topic,
                angle,
                project,
                now,
                now,
            ),
            f"creating a publish intent for run {run_id}",
        )
        return self.get_publish_intent(intent_id)  # type: ignore[return-value]

    def get_publish_intent(self, intent_id: str) -> PublishIntent | None:
        rows = self._read(
            "SELECT * FROM publish_intents WHERE intent_id = ?", (intent_id,)
        )
        return PublishIntent.from_row(rows[0]) if rows else None

    def get_intent_for_run(self, run_id: str) -> PublishIntent | None:
        rows = self._read(
            "SELECT * FROM publish_intents WHERE run_id = ?", (run_id,)
        )
        return PublishIntent.from_row(rows[0]) if rows else None

    def list_publish_intents(self, limit: int = 50) -> list[PublishIntent]:
        rows = self._read(
            "SELECT * FROM publish_intents ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [PublishIntent.from_row(row) for row in rows]

    def find_intent_by_content_hash(self, content_hash: str) -> PublishIntent | None:
        """The most recent intent for this exact content, if any.

        Exists so a caller can ask *"has this text been sent, or might it have
        been?"* **before** spending a request on it. The lookup is written to
        agree with ``ux_publish_intents_unresolved_content``: the only intents
        that can be re-attempted are the ones that definitely failed, so a
        ``failed`` intent is not returned and anything else is.
        """
        rows = self._read(
            "SELECT * FROM publish_intents WHERE content_hash = ? "
            "AND state <> 'failed' ORDER BY created_at DESC LIMIT 1",
            (content_hash,),
        )
        return PublishIntent.from_row(rows[0]) if rows else None

    def list_unresolved_intents(self, run_id: str | None = None
                                ) -> list[PublishIntent]:
        """Intents that have not reached a terminal state — oldest first.

        These are the recoverable cases, and the two states mean different
        things (see :meth:`mark_attempt_started`): ``intent_created`` is an
        attempt that never started, ``attempt_started`` is one whose outcome
        was never recorded and therefore may have published. Ordered by age so
        a recovery pass handles the oldest ambiguity first.
        """
        sql = (
            "SELECT * FROM publish_intents "
            "WHERE state IN ('intent_created', 'attempt_started')"
        )
        params: tuple = ()
        if run_id is not None:
            sql += " AND run_id = ?"
            params = (run_id,)
        rows = self._read(sql + " ORDER BY created_at", params)
        return [PublishIntent.from_row(row) for row in rows]

    def mark_attempt_started(self, intent_id: str) -> PublishIntent:
        """Mark that the API attempt is beginning — the last write before it.

        Only valid from ``intent_created``. The resulting distinction matters
        on recovery: an intent still at ``intent_created`` means the API was
        never called, whereas ``attempt_started`` with no publication record
        means the outcome is unknown and must not be retried.
        """
        with self._transaction(f"marking attempt started for {intent_id}"):
            intent = self.get_publish_intent(intent_id)
            if intent is None:
                raise StateStoreError(f"unknown publish intent {intent_id}")
            if intent.state is not PublishState.INTENT_CREATED:
                raise StateConstraintError(
                    f"publish intent {intent_id} is {intent.state.value}, not "
                    f"intent_created; refusing to start an attempt"
                )
            self._write(
                "UPDATE publish_intents SET state = 'attempt_started', "
                "updated_at = ? WHERE intent_id = ?",
                (utc_now_iso(), intent_id),
                f"marking attempt started for {intent_id}",
            )
        return self.get_publish_intent(intent_id)  # type: ignore[return-value]

    # -- publications -------------------------------------------------------

    def record_publication(self, intent_id: str, outcome: PublishState | str,
                           linkedin_post_id: str | None = None,
                           evidence_refs: Iterable[EvidenceRef] = (),
                           embedding: bytes | None = None,
                           ) -> Publication:
        """Resolve a publish intent, and record the evidence it was built on.

        The intent's state and the publication record are written in one
        transaction, so the two can never disagree about what happened.

        An outcome of ``published`` requires a post id: a response without one
        is an ambiguity or a failure, never a success. Duplicate evidence
        references are collapsed rather than rejected.

        ``embedding`` is the vector of the text that was sent, stored as opaque
        bytes. It is recorded here because this is the one moment the text and
        its outcome are known together; a later duplicate check compares
        against it instead of re-embedding the whole history. Step 6 owns its
        format; this layer never interprets it.
        """
        resolved = _coerce_enum(outcome, PublishState, "outcome")
        if resolved not in TERMINAL_PUBLISH_STATES:
            allowed = ", ".join(state.value for state in TERMINAL_PUBLISH_STATES)
            raise ValueError(
                f"outcome must be a terminal publish state ({allowed}); "
                f"got {resolved.value!r}"
            )
        if resolved is PublishState.PUBLISHED and not linkedin_post_id:
            raise ValueError(
                "a published outcome requires the LinkedIn post id; a post "
                "without one must be recorded as failed or unknown"
            )
        if resolved is not PublishState.PUBLISHED and linkedin_post_id:
            raise ValueError(
                f"outcome {resolved.value!r} cannot carry a LinkedIn post id"
            )

        publication_id = _new_id("pub")
        now = utc_now_iso()
        unique_evidence = _dedupe_evidence(evidence_refs)

        with self._transaction(f"recording publication for intent {intent_id}"):
            intent = self.get_publish_intent(intent_id)
            if intent is None:
                raise StateStoreError(
                    f"unknown publish intent {intent_id}: refusing to record a "
                    f"publication without its write-ahead intent"
                )
            if intent.state in TERMINAL_PUBLISH_STATES:
                raise StateConstraintError(
                    f"publish intent {intent_id} is already resolved as "
                    f"{intent.state.value}; refusing to resolve it twice"
                )
            self._write(
                "INSERT INTO publications (publication_id, intent_id, run_id, "
                "outcome, linkedin_post_id, content_hash, embedding, "
                "recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    publication_id,
                    intent_id,
                    intent.run_id,
                    resolved.value,
                    linkedin_post_id,
                    intent.content_hash,
                    embedding,
                    now,
                ),
                f"recording publication {publication_id}",
            )
            self._write(
                "UPDATE publish_intents SET state = ?, updated_at = ? "
                "WHERE intent_id = ?",
                (resolved.value, now, intent_id),
                f"resolving publish intent {intent_id}",
            )
            for ref in unique_evidence:
                self._write(
                    "INSERT INTO publication_evidence (publication_id, "
                    "source_path, content_hash) VALUES (?, ?, ?)",
                    (publication_id, ref.source_path, ref.content_hash),
                    f"recording evidence for publication {publication_id}",
                )
        return self.get_publication(publication_id)  # type: ignore[return-value]

    def get_publication(self, publication_id: str) -> Publication | None:
        rows = self._read(
            "SELECT * FROM publications WHERE publication_id = ?",
            (publication_id,),
        )
        if not rows:
            return None
        evidence = self._evidence_for([publication_id])
        return Publication.from_row(rows[0], evidence.get(publication_id, []))

    def get_publication_for_intent(self, intent_id: str) -> Publication | None:
        rows = self._read(
            "SELECT * FROM publications WHERE intent_id = ?", (intent_id,)
        )
        if not rows:
            return None
        evidence = self._evidence_for([rows[0]["publication_id"]])
        return Publication.from_row(rows[0], evidence.get(rows[0]["publication_id"], []))

    def list_publications(self, limit: int = 50) -> list[Publication]:
        """Most recently recorded first. Each carries its evidence references."""
        rows = self._read(
            "SELECT * FROM publications ORDER BY recorded_at DESC LIMIT ?",
            (limit,),
        )
        evidence = self._evidence_for([row["publication_id"] for row in rows])
        return [
            Publication.from_row(row, evidence.get(row["publication_id"], []))
            for row in rows
        ]

    def list_publication_records(self, *, since: str | None = None,
                                 outcome: PublishState | str | None = None,
                                 limit: int | None = None,
                                 ) -> list[PublicationRecord]:
        """Publications joined to the intents they resolved, newest first.

        This is the read the publishing-history service is built on: the
        questions it answers ("which topics did I use?", "which projects have I
        talked about?") are about what the *intent* said, and that is the table
        the answer lives in. Returning it as a typed join keeps the SQL here
        rather than in the publishing layer, where it would be a second place
        that knows the schema.

        ``since`` is an inclusive lower bound on ``recorded_at`` and ``limit``
        is optional, so a caller can ask for "everything in the last N days"
        without silently truncating an overuse count.
        """
        sql = (
            "SELECT p.publication_id, p.intent_id, p.run_id, p.outcome, "
            "p.linkedin_post_id, p.content_hash, p.embedding, p.recorded_at, "
            "i.topic, i.angle, i.project "
            "FROM publications p "
            "JOIN publish_intents i ON i.intent_id = p.intent_id"
        )
        conditions: list[str] = []
        params: list = []
        if since is not None:
            conditions.append("p.recorded_at >= ?")
            params.append(since)
        if outcome is not None:
            conditions.append("p.outcome = ?")
            params.append(_coerce_enum(outcome, PublishState, "outcome").value)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY p.recorded_at DESC, p.publication_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self._read(sql, tuple(params))
        evidence = self._evidence_for([row["publication_id"] for row in rows])
        return [
            PublicationRecord.from_row(row, evidence.get(row["publication_id"], []))
            for row in rows
        ]

    def _evidence_for(
        self, publication_ids: Sequence[str]
    ) -> dict[str, list[EvidenceRef]]:
        """Evidence references for several publications, in one query.

        Ordered by ``(source_path, content_hash)`` so a stored publication
        reads back identically every time — a stable order is what lets an
        audit compare two runs' evidence without spurious diffs.
        """
        if not publication_ids:
            return {}
        placeholders = ", ".join("?" * len(publication_ids))
        rows = self._read(
            f"SELECT publication_id, source_path, content_hash "
            f"FROM publication_evidence WHERE publication_id IN ({placeholders}) "
            f"ORDER BY source_path, content_hash",
            tuple(publication_ids),
        )
        grouped: dict[str, list[EvidenceRef]] = {}
        for row in rows:
            grouped.setdefault(row["publication_id"], []).append(
                EvidenceRef(
                    source_path=row["source_path"],
                    content_hash=row["content_hash"],
                )
            )
        return grouped

    # -- credential expiry ---------------------------------------------------

    def record_credential_expiry(self, credential: str, expires_at: str,
                                 issued_at: str | None = None,
                                 derived_from: CredentialDerivation | str = (
                                     CredentialDerivation.ID_TOKEN_IAT),
                                 source_mtime: str = "",
                                 ) -> CredentialExpiry:
        """Record when a stored credential expires.

        Idempotent per credential: the row is replaced, because a credential
        has exactly one expiry and keeping history here would make "when does
        it expire" a question with several answers. The issuance time and the
        evidence it came from are stored *with* it, so a caller can never read
        an expiry without also being able to see how much it can be trusted
        (``PLAN.md`` Step 5).

        This is the only write the LinkedIn integration makes. It is a fact
        read from the credential, not a claim that something was published —
        publication records belong to Step 6.
        """
        if not credential.strip():
            raise ValueError("credential must be non-empty")
        source = _coerce_enum(derived_from, CredentialDerivation, "derived_from")
        now = utc_now_iso()
        self._write(
            "INSERT INTO linkedin_credential_expiry (credential, expires_at, "
            "issued_at, derived_from, source_mtime, recorded_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (credential) DO UPDATE SET "
            "expires_at = excluded.expires_at, "
            "issued_at = excluded.issued_at, "
            "derived_from = excluded.derived_from, "
            "source_mtime = excluded.source_mtime, "
            "updated_at = excluded.updated_at",
            (credential, expires_at, issued_at, source.value, source_mtime,
             now, now),
            f"recording the expiry of credential {credential}",
        )
        return self.get_credential_expiry(credential)  # type: ignore[return-value]

    def get_credential_expiry(self, credential: str) -> CredentialExpiry | None:
        rows = self._read(
            "SELECT * FROM linkedin_credential_expiry WHERE credential = ?",
            (credential,),
        )
        return CredentialExpiry.from_row(rows[0]) if rows else None

    def list_credential_expiries(self) -> list[CredentialExpiry]:
        rows = self._read(
            "SELECT * FROM linkedin_credential_expiry ORDER BY credential"
        )
        return [CredentialExpiry.from_row(row) for row in rows]

    # -- operational failures -----------------------------------------------

    def record_failure(self, phase: str, error_category: str, message: str,
                       retryable: bool = False,
                       requires_human_intervention: bool = False,
                       run_id: str | None = None,
                       workflow: Workflow | str | None = None,
                       dedupe_key: str | None = None,
                       ) -> OperationalFailure:
        """Persist a structured failure. Never a log line, never swallowed.

        Passing a ``dedupe_key`` makes repeated identical failures increment
        one record's ``occurrence_count`` instead of creating unbounded rows.
        The **first** occurrence always creates the row, so deduplication can
        never hide a new problem — only quiet its repetitions.
        """
        if not phase.strip():
            raise ValueError("phase must be non-empty")
        name = None
        if workflow is not None:
            name = workflow.value if isinstance(workflow, Workflow) else str(workflow)
        now = utc_now_iso()
        failure_id = _new_id("fail")
        self._write(
            "INSERT INTO operational_failures (failure_id, run_id, workflow, "
            "phase, error_category, message, retryable, "
            "requires_human_intervention, dedupe_key, occurrence_count, "
            "first_seen_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) "
            "ON CONFLICT (dedupe_key) DO UPDATE SET "
            "occurrence_count = occurrence_count + 1, "
            "last_seen_at = excluded.last_seen_at",
            (
                failure_id,
                run_id,
                name,
                phase,
                error_category,
                message,
                int(bool(retryable)),
                int(bool(requires_human_intervention)),
                dedupe_key,
                now,
                now,
            ),
            f"recording a failure in phase {phase}",
        )
        if dedupe_key is None:
            stored_id = failure_id
        else:
            found = self._read(
                "SELECT failure_id FROM operational_failures WHERE dedupe_key = ?",
                (dedupe_key,),
            )
            stored_id = found[0]["failure_id"] if found else failure_id
        return self.get_failure(stored_id)  # type: ignore[return-value]

    def get_failure(self, failure_id: str) -> OperationalFailure | None:
        rows = self._read(
            "SELECT * FROM operational_failures WHERE failure_id = ?",
            (failure_id,),
        )
        return OperationalFailure.from_row(rows[0]) if rows else None

    def list_failures(self, run_id: str | None = None,
                      limit: int = 50) -> list[OperationalFailure]:
        if run_id is None:
            rows = self._read(
                "SELECT * FROM operational_failures ORDER BY last_seen_at "
                "DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self._read(
                "SELECT * FROM operational_failures WHERE run_id = ? "
                "ORDER BY last_seen_at DESC LIMIT ?",
                (run_id, limit),
            )
        return [OperationalFailure.from_row(row) for row in rows]

    # -- notifications ------------------------------------------------------

    def record_notification(self, recipient: str, subject: str,
                            delivery_state: DeliveryState | str,
                            failure_id: str | None = None,
                            run_id: str | None = None,
                            transport: str = "smtp",
                            smtp_config: str | None = None,
                            error_message: str | None = None,
                            ) -> Notification:
        """Record one notification delivery attempt and its outcome.

        This row is deliberately separate from the failure it reports: a
        delivery failure must never replace or erase the original workflow
        failure, and the two must stay separately observable.
        """
        state = _coerce_enum(delivery_state, DeliveryState, "delivery_state")
        now = utc_now_iso()
        notification_id = _new_id("notif")
        self._write(
            "INSERT INTO notifications (notification_id, failure_id, run_id, "
            "recipient, subject, transport, smtp_config, delivery_state, "
            "error_message, created_at, attempted_at, delivered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                notification_id,
                failure_id,
                run_id,
                recipient,
                subject,
                transport,
                smtp_config,
                state.value,
                error_message,
                now,
                now,
                now if state is DeliveryState.SENT else None,
            ),
            f"recording a {state.value} notification to {recipient}",
        )
        return self.get_notification(notification_id)  # type: ignore[return-value]

    def update_notification_delivery(self, notification_id: str,
                                     delivery_state: DeliveryState | str,
                                     error_message: str | None = None,
                                     ) -> Notification:
        """Resolve a notification left at ``pending`` by an earlier attempt."""
        state = _coerce_enum(delivery_state, DeliveryState, "delivery_state")
        now = utc_now_iso()
        cursor = self._write(
            "UPDATE notifications SET delivery_state = ?, error_message = ?, "
            "attempted_at = ?, delivered_at = ? WHERE notification_id = ?",
            (
                state.value,
                error_message,
                now,
                now if state is DeliveryState.SENT else None,
                notification_id,
            ),
            f"updating notification {notification_id}",
        )
        if cursor.rowcount == 0:
            raise StateStoreError(f"unknown notification {notification_id}")
        return self.get_notification(notification_id)  # type: ignore[return-value]

    def get_notification(self, notification_id: str) -> Notification | None:
        rows = self._read(
            "SELECT * FROM notifications WHERE notification_id = ?",
            (notification_id,),
        )
        return Notification.from_row(rows[0]) if rows else None

    def list_notifications(self, run_id: str | None = None,
                           delivery_state: DeliveryState | str | None = None,
                           failure_id: str | None = None,
                           limit: int = 50) -> list[Notification]:
        """Delivery records, newest first, optionally filtered.

        ``failure_id`` was added in Step 7 for the notification layer's noise
        control: "was *this* failure already reported a moment ago" is a
        question only a read filtered by the failure can answer, and a failure
        that recurs across runs keeps the ``failure_id`` it was first recorded
        with while its ``occurrence_count`` grows.
        """
        clauses: list[str] = []
        params: list[object] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if failure_id is not None:
            clauses.append("failure_id = ?")
            params.append(failure_id)
        if delivery_state is not None:
            state = _coerce_enum(delivery_state, DeliveryState, "delivery_state")
            clauses.append("delivery_state = ?")
            params.append(state.value)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(limit)
        rows = self._read(
            f"SELECT * FROM notifications {where}ORDER BY created_at DESC "
            f"LIMIT ?",
            tuple(params),
        )
        return [Notification.from_row(row) for row in rows]

    # -- locks --------------------------------------------------------------

    def get_lock(self, lock_name: str) -> Lock | None:
        rows = self._read("SELECT * FROM locks WHERE lock_name = ?", (lock_name,))
        return Lock.from_row(rows[0]) if rows else None

    def acquire_lock(self, lock_name: str, owner: str,
                     ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
                     ) -> LockAcquisition:
        """Try to take a lock, reclaiming it if the previous holder is gone.

        The whole check-and-take runs in one transaction, so two processes
        racing for the same lock cannot both win. A lock whose ``expires_at``
        has passed is reclaimed and the result is flagged
        ``recovered_stale`` — recovery is reported, never silent, and a held
        lock is never quietly overridden.
        """
        if not owner.strip():
            raise ValueError("owner must be non-empty")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must not be negative")
        now = utc_now_iso()
        expires = iso_in(ttl_seconds)
        with self._transaction(f"acquiring lock {lock_name}"):
            rows = self._read(
                "SELECT * FROM locks WHERE lock_name = ?", (lock_name,)
            )
            if not rows:
                self._write(
                    "INSERT INTO locks (lock_name, owner, acquired_at, "
                    "heartbeat_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (lock_name, owner, now, now, expires),
                    f"acquiring lock {lock_name}",
                )
                return LockAcquisition(
                    acquired=True, lock=self.get_lock(lock_name)
                )
            held = Lock.from_row(rows[0])
            if held.expires_at > now:
                return LockAcquisition(
                    acquired=False, lock=held, holder=held.owner
                )
            self._write(
                "UPDATE locks SET owner = ?, acquired_at = ?, heartbeat_at = ?, "
                "expires_at = ? WHERE lock_name = ?",
                (owner, now, now, expires, lock_name),
                f"reclaiming stale lock {lock_name}",
            )
            return LockAcquisition(
                acquired=True, recovered_stale=True, lock=self.get_lock(lock_name)
            )

    def release_lock(self, lock_name: str, owner: str) -> bool:
        """Release a lock held by ``owner``. False if someone else holds it."""
        cursor = self._write(
            "DELETE FROM locks WHERE lock_name = ? AND owner = ?",
            (lock_name, owner),
            f"releasing lock {lock_name}",
        )
        return cursor.rowcount > 0

    def renew_lock(self, lock_name: str, owner: str,
                   ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS) -> Lock:
        """Extend a held lock. Raises if this owner no longer holds it.

        Failing loudly is the point: a workflow that silently believes it
        still holds a lock it has lost is exactly the overlapping run the
        lock exists to prevent.
        """
        now = utc_now_iso()
        cursor = self._write(
            "UPDATE locks SET heartbeat_at = ?, expires_at = ? "
            "WHERE lock_name = ? AND owner = ?",
            (now, iso_in(ttl_seconds), lock_name, owner),
            f"renewing lock {lock_name}",
        )
        if cursor.rowcount == 0:
            raise StateStoreError(
                f"cannot renew lock {lock_name}: it is not held by {owner!r}"
            )
        return self.get_lock(lock_name)  # type: ignore[return-value]


def _dedupe_evidence(refs: Iterable[EvidenceRef]) -> list[EvidenceRef]:
    """Collapse duplicate references, preserving first-seen order."""
    seen: set[tuple[str, str]] = set()
    unique: list[EvidenceRef] = []
    for ref in refs:
        key = (ref.source_path, ref.content_hash)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique
