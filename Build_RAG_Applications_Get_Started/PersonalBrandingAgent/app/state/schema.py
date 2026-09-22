"""Schema definition and the forward-only migration runner.

The store is a single SQLite file. Schema changes are expressed as ordered,
append-only :class:`Migration` values; the applied set is recorded in
``schema_version`` so a migration never runs twice. There is no down path —
reversing a migration on an audit store would mean destroying the record of
what the system did.

Rules the schema itself enforces (not application code):

======================================  =====================================
Guarantee                               Enforcement
======================================  =====================================
A run ends as one of exactly three      ``workflow_runs.outcome`` CHECK
outcomes, and only once it has finished ``(outcome IS NULL) = (finished_at IS NULL)``
A publish state is one of five values   ``publish_intents.state`` CHECK
At most one publish intent per run      ``ux_publish_intents_run``
At most one unresolved intent per       ``ux_publish_intents_unresolved_content``
content hash
At most one publication per intent      ``publications.intent_id`` UNIQUE
"Published" means LinkedIn returned a   ``(outcome = 'published') =
post id                                 (linkedin_post_id IS NOT NULL)``
A checkpoint moves only with its        ``(last_revision IS NULL) =
timestamp                               (last_synced_at IS NULL)``
A lifecycle is one of four values       ``source_lifecycle.lifecycle`` CHECK
A delivery state is one of three values ``notifications.delivery_state`` CHECK
A "sent" notification has a delivery    ``(delivery_state = 'sent') =
time                                    (delivered_at IS NOT NULL)``
A credential expiry was derived, not    ``linkedin_credential_expiry``
asserted                                ``.derived_from`` CHECK
One holder per lock                     ``locks.lock_name`` PRIMARY KEY
======================================  =====================================

Note what is deliberately *not* constrained: ``workflow_runs.workflow`` and
``operational_failures.error_category``. Their vocabularies belong to the
workflow layer (Step 11) and the LinkedIn/generation layers (Steps 5, 8) and
would only have to be migrated again here. The two vocabularies the roadmap
does insist on — run outcome and publish state — are constrained.
"""
import sqlite3
from dataclasses import dataclass

from app.errors import StateStoreError
from app.state.models import utc_now_iso


@dataclass(frozen=True)
class Migration:
    """One forward-only schema change."""

    version: int
    description: str
    statements: tuple[str, ...]


#: The schema-version ledger. Created outside the migrations themselves so
#: the runner always has somewhere to record what it has applied.
SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at  TEXT NOT NULL
)
"""


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="initial operational state schema",
        statements=(
            # --- runs -------------------------------------------------------
            """
            CREATE TABLE workflow_runs (
                run_id       TEXT PRIMARY KEY,
                workflow     TEXT NOT NULL,
                started_at   TEXT NOT NULL,
                finished_at  TEXT,
                outcome      TEXT CHECK (outcome IN (
                                 'DO_NOT_PUBLISH',
                                 'WORKFLOW_FAILED',
                                 'REQUIRES_HUMAN_INTERVENTION')),
                failed_phase TEXT,
                -- A run has an outcome exactly when it has finished. An
                -- unfinished run (outcome NULL) is a real, detectable state:
                -- it is how an interrupted run is found on the next start.
                CHECK ((outcome IS NULL) = (finished_at IS NULL))
            )
            """,
            "CREATE INDEX ix_workflow_runs_started "
            "ON workflow_runs (started_at DESC)",
            "CREATE INDEX ix_workflow_runs_outcome "
            "ON workflow_runs (outcome)",
            # --- synchronization checkpoints ---------------------------------
            """
            CREATE TABLE sync_checkpoints (
                source_name     TEXT PRIMARY KEY,
                last_revision   TEXT,
                last_synced_at  TEXT,
                last_attempt_at TEXT NOT NULL,
                last_outcome    TEXT NOT NULL CHECK (
                                    last_outcome IN ('SUCCEEDED', 'FAILED')),
                updated_at      TEXT NOT NULL,
                -- A revision and the time it was processed travel together:
                -- a source that has never synced successfully has neither.
                CHECK ((last_revision IS NULL) = (last_synced_at IS NULL))
            )
            """,
            # --- source lifecycle --------------------------------------------
            """
            CREATE TABLE source_lifecycle (
                source_name TEXT PRIMARY KEY,
                lifecycle   TEXT NOT NULL CHECK (lifecycle IN (
                                'ACTIVE', 'PAUSED', 'COMPLETED', 'PLANNED')),
                note        TEXT,
                updated_at  TEXT NOT NULL
            )
            """,
            # --- publish intents ---------------------------------------------
            """
            CREATE TABLE publish_intents (
                intent_id    TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL REFERENCES workflow_runs (run_id),
                state        TEXT NOT NULL CHECK (state IN (
                                 'intent_created',
                                 'attempt_started',
                                 'published',
                                 'failed',
                                 'unknown_requires_review')),
                content      TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                topic        TEXT,
                angle        TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
            """,
            # MAX_PUBLISHES_PER_RUN = 1, enforced by the database rather than
            # by the workflow remembering to check.
            "CREATE UNIQUE INDEX ux_publish_intents_run "
            "ON publish_intents (run_id)",
            # At most one *unresolved* intent per piece of content, across
            # runs. The intent is written before the API call, so this is the
            # only place where "the same post cannot go out twice" can
            # actually prevent the call rather than merely record it after
            # the fact. A `failed` intent drops out of the index: an attempt
            # that definitively did not publish must not block the content
            # forever. `unknown_requires_review` deliberately stays in it.
            "CREATE UNIQUE INDEX ux_publish_intents_unresolved_content "
            "ON publish_intents (content_hash) WHERE state <> 'failed'",
            "CREATE INDEX ix_publish_intents_created "
            "ON publish_intents (created_at DESC)",
            # --- publications ------------------------------------------------
            """
            CREATE TABLE publications (
                publication_id   TEXT PRIMARY KEY,
                intent_id        TEXT NOT NULL UNIQUE
                                   REFERENCES publish_intents (intent_id),
                run_id           TEXT NOT NULL REFERENCES workflow_runs (run_id),
                outcome          TEXT NOT NULL CHECK (outcome IN (
                                   'published',
                                   'failed',
                                   'unknown_requires_review')),
                linkedin_post_id TEXT,
                content_hash     TEXT NOT NULL,
                recorded_at      TEXT NOT NULL,
                -- A response without a post id is never success, and a
                -- failure never carries an id.
                CHECK ((outcome = 'published') = (linkedin_post_id IS NOT NULL))
            )
            """,
            "CREATE INDEX ix_publications_recorded "
            "ON publications (recorded_at DESC)",
            "CREATE INDEX ix_publications_content_hash "
            "ON publications (content_hash)",
            """
            CREATE TABLE publication_evidence (
                publication_id TEXT NOT NULL
                                 REFERENCES publications (publication_id),
                source_path    TEXT NOT NULL,
                content_hash   TEXT NOT NULL,
                PRIMARY KEY (publication_id, source_path, content_hash)
            )
            """,
            # --- failures -----------------------------------------------------
            """
            CREATE TABLE operational_failures (
                failure_id    TEXT PRIMARY KEY,
                run_id        TEXT REFERENCES workflow_runs (run_id),
                workflow      TEXT,
                phase         TEXT NOT NULL,
                error_category TEXT NOT NULL,
                message       TEXT NOT NULL,
                retryable     INTEGER NOT NULL CHECK (retryable IN (0, 1)),
                requires_human_intervention INTEGER NOT NULL
                                CHECK (requires_human_intervention IN (0, 1)),
                dedupe_key    TEXT,
                occurrence_count INTEGER NOT NULL DEFAULT 1
                                CHECK (occurrence_count >= 1),
                first_seen_at TEXT NOT NULL,
                last_seen_at  TEXT NOT NULL
            )
            """,
            "CREATE INDEX ix_failures_run ON operational_failures (run_id)",
            # One row per dedupe key, so a recurring failure accumulates an
            # occurrence count on a single record instead of producing an
            # unbounded stream of rows. NULL keys never conflict, so failures
            # recorded without a key are always distinct rows.
            "CREATE UNIQUE INDEX ux_failures_dedupe_key "
            "ON operational_failures (dedupe_key)",
            # --- notifications ------------------------------------------------
            """
            CREATE TABLE notifications (
                notification_id TEXT PRIMARY KEY,
                failure_id      TEXT
                                  REFERENCES operational_failures (failure_id),
                run_id          TEXT REFERENCES workflow_runs (run_id),
                recipient       TEXT NOT NULL,
                subject         TEXT NOT NULL,
                transport       TEXT NOT NULL,
                smtp_config     TEXT,
                delivery_state  TEXT NOT NULL CHECK (delivery_state IN (
                                    'pending', 'sent', 'failed')),
                error_message   TEXT,
                created_at      TEXT NOT NULL,
                attempted_at    TEXT,
                delivered_at    TEXT,
                CHECK ((delivery_state = 'sent') = (delivered_at IS NOT NULL))
            )
            """,
            "CREATE INDEX ix_notifications_run ON notifications (run_id)",
            "CREATE INDEX ix_notifications_delivery "
            "ON notifications (delivery_state)",
            # --- locks --------------------------------------------------------
            """
            CREATE TABLE locks (
                lock_name    TEXT PRIMARY KEY,
                owner        TEXT NOT NULL,
                acquired_at  TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL,
                expires_at   TEXT NOT NULL,
                CHECK (expires_at >= acquired_at)
            )
            """,
        ),
    ),
    Migration(
        version=2,
        description="record LinkedIn credential expiry",
        statements=(
            # Step 5. The stored LinkedIn credential carries a *duration*
            # (``expires_in``), never an absolute expiry, so the expiry has to
            # be derived from when it was issued. Deriving it on every run
            # would work only while the token file is never touched; recording
            # it once — together with the timestamp it was derived from — lets
            # a run compare, notice the credential has been re-created, and
            # re-derive instead of trusting a stale row.
            #
            # The row is a fact read from the credential, not a claim about
            # something the system did, and it is the *only* thing the
            # integration layer writes: publication records belong to Step 6,
            # and the integration never records publishing success on its own
            # authority.
            """
            CREATE TABLE linkedin_credential_expiry (
                credential    TEXT PRIMARY KEY,
                expires_at    TEXT NOT NULL,
                issued_at     TEXT,
                derived_from  TEXT NOT NULL CHECK (derived_from IN (
                                  'id_token_iat', 'file_mtime')),
                source_mtime  TEXT NOT NULL,
                recorded_at   TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                CHECK (expires_at >= issued_at OR issued_at IS NULL)
            )
            """,
        ),
    ),
    Migration(
        version=3,
        description="record the project a post is about, and the embedding of "
                    "what was published, for the Step 6 duplicate checks",
        statements=(
            # Step 6. Three duplicate checks need three different kinds of
            # stored data, and two of them need a column that Step 1 did not
            # anticipate:
            #
            # * exact     -> ``content_hash`` (Step 1, unchanged);
            # * near      -> the embedding of *what was published*, so a later
            #                candidate can be compared against real posts
            #                without re-embedding the entire history;
            # * overuse   -> ``topic`` (Step 1) and the project the post was
            #                about, which only the caller knows and which
            #                cannot be derived from a content hash or from a
            #                source path without guessing.
            #
            # ``publications.content`` is deliberately *not* added: the text
            # already lives on the intent (``publications.intent_id`` is
            # UNIQUE, so the join is 1:1), and duplicating it would let the two
            # copies disagree about what was published.
            "ALTER TABLE publish_intents ADD COLUMN project TEXT",
            "ALTER TABLE publications ADD COLUMN embedding BLOB",
        ),
    ),
)

#: The schema version this code expects. Bump only by appending a migration.
SCHEMA_VERSION: int = max(migration.version for migration in MIGRATIONS)

#: Tables the schema owns, in dependency order. Used by tests and by any
#: future integrity check; not used to create anything.
TABLES: tuple[str, ...] = (
    "workflow_runs",
    "sync_checkpoints",
    "source_lifecycle",
    "publish_intents",
    "publications",
    "publication_evidence",
    "operational_failures",
    "notifications",
    "locks",
    "linkedin_credential_expiry",
)


def applied_versions(conn: sqlite3.Connection) -> list[int]:
    """Versions recorded in ``schema_version``, ascending."""
    rows = conn.execute("SELECT version FROM schema_version ORDER BY version")
    return [row[0] for row in rows]


def current_version(conn: sqlite3.Connection) -> int:
    """The highest applied schema version, or 0 for an unmigrated store."""
    versions = applied_versions(conn)
    return versions[-1] if versions else 0


def ensure_schema(conn: sqlite3.Connection) -> int:
    """Bring ``conn`` up to :data:`SCHEMA_VERSION` and return that version.

    Idempotent: a store already at the current version is left untouched.
    Each migration runs in its own transaction, so a failure part-way leaves
    the store at the last fully applied version rather than half-migrated.
    """
    known = [migration.version for migration in MIGRATIONS]
    conn.execute(SCHEMA_VERSION_DDL)
    applied = applied_versions(conn)

    unknown = [version for version in applied if version not in known]
    if unknown:
        raise StateStoreError(
            f"state store schema is newer than this code: found version(s) "
            f"{unknown}, this build knows {known}. Refusing to operate on a "
            f"store written by a newer version of the application."
        )

    # A gap means the ledger is inconsistent (a version was applied out of
    # order, or a row was removed). Applying the missing migration now could
    # apply it *after* a later one — refuse instead.
    if applied != list(range(1, len(applied) + 1)):
        raise StateStoreError(
            f"state store migration history is not contiguous: {applied}. "
            f"Refusing to migrate a store whose schema version ledger is "
            f"inconsistent."
        )

    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        _apply(conn, migration)
    return current_version(conn)


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    """Apply one migration and record it, atomically."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in migration.statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_version (version, description, applied_at) "
            "VALUES (?, ?, ?)",
            (migration.version, migration.description, utc_now_iso()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
