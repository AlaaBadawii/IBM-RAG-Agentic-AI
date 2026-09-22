"""Schema-level tests: the database itself carries the guarantees.

These tests deliberately bypass the typed store API and write raw SQL through
an independent connection. If a guarantee held only because Python checked it
first, none of these would fail — which is precisely what they exist to
detect. ``PLAN.md`` Step 1: "uniqueness constraints carry the correctness
guarantees, not application code".
"""
import shutil
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app import paths
from app.errors import StateConstraintError, StateStoreError
from app.state import SCHEMA_VERSION, TABLES, StateStore
from app.state import schema as schema_module


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "state_db" / "operational_state.db"


@pytest.fixture
def store(store_path):
    with StateStore(store_path) as opened:
        yield opened


@contextmanager
def raw_connection(path):
    """An independent connection to the same file.

    Foreign keys are switched on explicitly: they are per-connection, and this
    connection is not the store's.
    """
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


# --- creation and migration -----------------------------------------------

def test_store_creates_its_file_and_every_table(store, store_path):
    assert store_path.is_file()
    with raw_connection(store_path) as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert set(TABLES) <= names
    assert "schema_version" in names


def test_schema_version_is_recorded(store, store_path):
    with raw_connection(store_path) as conn:
        versions = [
            row["version"]
            for row in conn.execute("SELECT version FROM schema_version")
        ]
    assert versions == list(range(1, SCHEMA_VERSION + 1))


def test_migration_from_an_empty_file(store_path):
    """A brand-new, zero-byte database must migrate from scratch."""
    store_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(store_path)).close()  # an empty but existing file

    with StateStore(store_path) as store:
        assert store.schema_version == SCHEMA_VERSION
    with raw_connection(store_path) as conn:
        assert schema_module.current_version(conn) == SCHEMA_VERSION


def test_reopening_does_not_reapply_migrations(store_path):
    StateStore(store_path).close()
    with raw_connection(store_path) as conn:
        before = schema_module.applied_versions(conn)

    with StateStore(store_path) as reopened:
        assert reopened.schema_version == SCHEMA_VERSION

    with raw_connection(store_path) as conn:
        after = schema_module.applied_versions(conn)
    # One row per migration, not one per open.
    assert after == before


def test_store_written_by_a_newer_version_is_refused(store, store_path):
    with raw_connection(store_path) as conn:
        conn.execute(
            "INSERT INTO schema_version (version, description, applied_at) "
            "VALUES (999, 'from the future', '2026-01-01T00:00:00.000000+00:00')"
        )
        conn.commit()

    with pytest.raises(StateStoreError, match="newer than this code"):
        StateStore(store_path)


def test_gap_in_the_migration_ledger_is_refused(tmp_path, monkeypatch):
    # The probe is appended after every real migration rather than numbered
    # with a literal, so this test keeps testing "a gap is refused" as the
    # schema grows instead of colliding with the next migration added.
    probe_version = SCHEMA_VERSION + 1
    probe = schema_module.Migration(
        version=probe_version,
        description="probe",
        statements=("CREATE TABLE _probe (id INTEGER PRIMARY KEY)",),
    )
    monkeypatch.setattr(
        schema_module, "MIGRATIONS", schema_module.MIGRATIONS + (probe,)
    )
    path = tmp_path / "gapped.db"
    conn = sqlite3.connect(str(path))
    conn.isolation_level = None
    try:
        assert schema_module.ensure_schema(conn) == probe_version
        conn.execute("DELETE FROM schema_version WHERE version = 1")
        with pytest.raises(StateStoreError, match="not contiguous"):
            schema_module.ensure_schema(conn)
    finally:
        conn.close()


def test_journal_mode_is_wal(store_path):
    StateStore(store_path).close()
    with raw_connection(store_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_foreign_keys_are_declared_and_enforced(store_path):
    with StateStore(store_path) as store:
        with pytest.raises(StateConstraintError):
            # run_id references workflow_runs(run_id); this run does not exist.
            store.create_publish_intent("branding-does-not-exist", "text")

    with raw_connection(store_path) as conn:
        declared = {
            row["table"]
            for row in conn.execute("PRAGMA foreign_key_list(publications)")
        }
    assert "publish_intents" in declared


# --- constrained vocabularies ---------------------------------------------

def test_run_outcome_outside_the_vocabulary_is_rejected(store, store_path):
    run = store.start_run("branding")
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE workflow_runs SET outcome = 'SUCCEEDED' WHERE run_id = ?",
                (run.run_id,),
            )


def test_a_run_cannot_be_finished_without_an_outcome(store, store_path):
    run = store.start_run("branding")
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE workflow_runs SET finished_at = ? WHERE run_id = ?",
                ("2026-01-01T00:00:00.000000+00:00", run.run_id),
            )


def test_publish_state_outside_the_vocabulary_is_rejected(store, store_path):
    run = store.start_run("branding")
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO publish_intents (intent_id, run_id, state, content, "
                "content_hash, created_at, updated_at) "
                "VALUES ('i1', ?, 'maybe_later', 'text', 'hash', 'now', 'now')",
                (run.run_id,),
            )


def test_lifecycle_outside_the_vocabulary_is_rejected(store, store_path):
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO source_lifecycle (source_name, lifecycle, updated_at) "
                "VALUES ('ibm', 'DONE', 'now')"
            )


def test_delivery_state_outside_the_vocabulary_is_rejected(store, store_path):
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO notifications (notification_id, recipient, subject, "
                "transport, delivery_state, created_at) "
                "VALUES ('n1', 'a@b.c', 's', 'smtp', 'delivered', 'now')"
            )


def test_checkpoint_outcome_outside_the_vocabulary_is_rejected(store, store_path):
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sync_checkpoints (source_name, last_attempt_at, "
                "last_outcome, updated_at) VALUES ('ibm', 'now', 'PARTIAL', 'now')"
            )


# --- cross-column consistency ---------------------------------------------

def _intent_row(store, store_path):
    run = store.start_run("branding")
    with raw_connection(store_path) as conn:
        conn.execute(
            "INSERT INTO publish_intents (intent_id, run_id, state, content, "
            "content_hash, created_at, updated_at) "
            "VALUES ('i1', ?, 'attempt_started', 'text', 'hash', 'now', 'now')",
            (run.run_id,),
        )
        conn.commit()
    return run


def test_published_requires_a_post_id(store, store_path):
    run = _intent_row(store, store_path)
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO publications (publication_id, intent_id, run_id, "
                "outcome, content_hash, recorded_at) "
                "VALUES ('p1', 'i1', ?, 'published', 'hash', 'now')",
                (run.run_id,),
            )


def test_a_failure_cannot_carry_a_post_id(store, store_path):
    run = _intent_row(store, store_path)
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO publications (publication_id, intent_id, run_id, "
                "outcome, linkedin_post_id, content_hash, recorded_at) "
                "VALUES ('p1', 'i1', ?, 'failed', 'urn:li:share:9', 'hash', 'now')",
                (run.run_id,),
            )


def test_a_sent_notification_needs_a_delivery_time(store, store_path):
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO notifications (notification_id, recipient, subject, "
                "transport, delivery_state, created_at) "
                "VALUES ('n1', 'a@b.c', 's', 'smtp', 'sent', 'now')"
            )


def test_a_checkpoint_revision_needs_its_timestamp(store, store_path):
    with raw_connection(store_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sync_checkpoints (source_name, last_revision, "
                "last_attempt_at, last_outcome, updated_at) "
                "VALUES ('ibm', 'abc123', 'now', 'SUCCEEDED', 'now')"
            )


# --- timestamps and location ----------------------------------------------

def test_timestamps_are_stored_as_utc(store):
    run = store.start_run("branding")
    moment = datetime.fromisoformat(run.started_at)
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_the_default_location_is_gitignored():
    """Acceptance: the store is created in a gitignored location."""
    assert paths.STATE_DB_PATH.is_relative_to(paths.PROJECT_ROOT)
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available to check ignore rules")

    ignored = subprocess.run(
        [git, "check-ignore", "--quiet", str(paths.STATE_DB_PATH)],
        cwd=paths.PROJECT_ROOT,
        capture_output=True,
    )
    assert ignored.returncode == 0, (
        "the operational state store must be gitignored, like chroma_db/ and logs/"
    )
    # Control: the knowledge corpus is committed, so it must not be ignored.
    tracked = subprocess.run(
        [git, "check-ignore", "--quiet", str(paths.DATA_DIR / "evidence")],
        cwd=paths.PROJECT_ROOT,
        capture_output=True,
    )
    assert tracked.returncode == 1


def test_the_default_path_is_used_when_none_is_given(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.state.store.STATE_DB_PATH", tmp_path / "state_db" / "default.db"
    )
    with StateStore() as store:
        assert store.path == tmp_path / "state_db" / "default.db"


def test_operational_state_never_reaches_the_vector_store(tmp_path):
    """The state layer must not even import the knowledge layer.

    Checked in a subprocess so that other test modules having already
    imported Chroma cannot mask the result.
    """
    code = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(paths.PROJECT_ROOT)!r})",
            "from app.state import StateStore, Workflow",
            "with StateStore(" + repr(str(tmp_path / "s.db")) + ") as store:",
            "    run = store.start_run(Workflow.BRANDING)",
            "    store.create_publish_intent(run.run_id, 'a post')",
            "leaked = [m for m in sys.modules if m.split('.')[0] in "
            "{'chromadb', 'langchain_chroma', 'sentence_transformers'}"
            " or m.startswith(('app.ingestion', 'app.retrieval'))]",
            "print(','.join(sorted(leaked)))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        f"the state store pulled in the knowledge layer: {result.stdout.strip()}"
    )
