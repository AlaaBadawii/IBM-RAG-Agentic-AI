"""The Improvement Lab's isolation boundary, pinned as tests.

``app/improvement`` is meant to sit *beside* production: it reads a copy of the
operational database, evaluates frozen fixtures, and can never publish, notify,
migrate, or write production state. Two kinds of assertion prove that here.

*Structural.* An AST scan over every module in the package, for the reason
``tests/test_agent_boundaries.py`` gives about its own package: *"this module
cannot reach a store" is a property that cannot silently regress, whereas "no
test observed a write" only proves that no test looked.* If there is no import
path to the publisher, the store, or a transport, there is nothing to remember
to check.

*Behavioural.* The collector is run against a real SQLite file and the source is
proved byte-identical afterwards; the evaluator is run with ``StateStore``
monkeypatched to explode and is proved not to touch it.
"""
import ast
import hashlib
import sqlite3
from pathlib import Path

import pytest

IMPROVEMENT_PACKAGE = (
    Path(__file__).resolve().parents[1] / "app" / "improvement"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Import roots the Lab must have no path to, and why each one is here.
#:
#: ``app.publishing`` / ``app.notify``   the Lab measures; it never publishes
#:                                       or notifies.
#: ``app.state``                         evidence is read from a raw read-only
#:                                       copy — never a ``StateStore``, which
#:                                       can run migrations.
#: ``app.workflows`` / ``app.agent``     the production decision paths. The Lab
#:                                       is not on them.
#: ``app.integrations`` / ``app.sync`` / ``app.ingestion`` / ``app.sources``
#:                                       LinkedIn and the knowledge layer.
#: ``smtplib`` / ``socket`` / ``requests`` / ``httpx`` / ``urllib``
#:                                       transports. Nothing here egresses.
#: model SDKs                            no live model is invoked in this stage.
FORBIDDEN = (
    "app.publishing", "app.notify", "app.state", "app.workflows",
    "app.agent", "app.integrations", "app.sync", "app.ingestion",
    "app.sources",
    "smtplib", "socket", "requests", "httpx", "urllib", "urllib3",
    "google", "genai", "openai", "anthropic", "langchain", "langgraph",
    "chromadb", "transformers", "sentence_transformers",
)

#: The only ``app.*`` roots the package may import, and what each is for.
ALLOWED_APP = (
    "app.improvement",   # itself
    "app.context",       # builds the real context for a frozen case
    "app.generation",    # value types: GeneratedPost, EvidenceCitation
    "app.verification",  # the real gate: verify()
    "app.retrieval.models",  # value types only: RetrievalResult/RetrievedDocument
    "app.paths",         # reads PROJECT_ROOT; no store handle
)

IMPROVEMENT_MODULES = sorted(IMPROVEMENT_PACKAGE.glob("*.py"))


def _imported(module: Path) -> list[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("module", IMPROVEMENT_MODULES,
                         ids=lambda path: path.name)
def test_the_lab_reaches_no_layer_it_must_not(module):
    """No publisher, no store, no transport, no model SDK, no production path."""
    offenders = [
        name for name in _imported(module)
        if any(name == bad or name.startswith(f"{bad}.")
               for bad in FORBIDDEN)
    ]
    assert not offenders, (
        f"{module.name} reaches a layer the Lab must not: {offenders}"
    )


@pytest.mark.parametrize("module", IMPROVEMENT_MODULES,
                         ids=lambda path: path.name)
def test_the_lab_imports_only_accounted_for_app_layers(module):
    """The positive half: every ``app.*`` import is one of the allowed roots.

    A new ``app.*`` import has to be added here deliberately, so a change can
    never quietly widen the Lab's reach into production.
    """
    offenders = [
        name for name in _imported(module)
        if name.startswith("app.")
        and not any(name == good or name.startswith(f"{good}.")
                    for good in ALLOWED_APP)
    ]
    assert not offenders, (
        f"{module.name} imports a layer outside the Lab's remit: {offenders}"
    )


def _make_operational_db(path: Path) -> None:
    """A minimal but valid operational DB: ledger + one allowlisted table."""
    with sqlite3.connect(str(path)) as conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (13)")
        conn.execute(
            "CREATE TABLE workflow_runs ("
            "run_id TEXT, workflow TEXT, outcome TEXT, "
            "started_at TEXT, finished_at TEXT, secret_column TEXT)"
        )
        conn.execute(
            "INSERT INTO workflow_runs VALUES "
            "('run-1', 'branding', 'PUBLISHED', 't0', 't1', 'do-not-export')"
        )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_collect_never_mutates_the_source_database(tmp_path):
    """The source is opened read-only and is byte-identical afterwards.

    No rollback journal or WAL is left beside it either — the online backup API
    is used precisely so a live file is never written to or torn.
    """
    source = tmp_path / "operational_state.db"
    _make_operational_db(source)
    before = _digest(source)

    from app.improvement.evidence import collect_evidence

    bundle = collect_evidence(source, tmp_path / "private")

    assert _digest(source) == before
    # No rollback journal or WAL is left beside the source.
    sidecars = sorted(
        p.name for p in tmp_path.iterdir()
        if p.name.startswith("operational_state.db-")
    )
    assert sidecars == []
    assert bundle.schema_version == 13
    assert "workflow_runs" in bundle.tables_available


def test_collector_exports_only_allowlisted_columns(tmp_path):
    """A column not on the allowlist never reaches an export file."""
    source = tmp_path / "operational_state.db"
    _make_operational_db(source)

    from app.improvement.evidence import collect_evidence

    bundle = collect_evidence(source, tmp_path / "private")
    exported = Path(bundle.exports["workflow_runs"]).read_text(encoding="utf-8")
    assert "do-not-export" not in exported
    assert "secret_column" not in exported


def test_collector_refuses_a_copy_newer_than_it_understands(tmp_path):
    """A future schema is refused rather than misread."""
    source = tmp_path / "future.db"
    with sqlite3.connect(str(source)) as conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (9999)")

    from app.improvement.evidence import EvidenceError, collect_evidence

    with pytest.raises(EvidenceError, match="newer than"):
        collect_evidence(source, tmp_path / "private")


def test_snapshot_refuses_to_overwrite_its_own_source(tmp_path):
    """A source and destination that are the same file is a refused no-op."""
    source = tmp_path / "operational_state.db"
    _make_operational_db(source)

    from app.improvement.evidence import EvidenceError, snapshot_database

    with pytest.raises(EvidenceError, match="same file"):
        snapshot_database(source, source)


def test_evaluate_never_opens_a_state_store(tmp_path, monkeypatch):
    """The evaluator runs with ``StateStore`` made fatal, and never trips it."""
    import app.state.store as store_module

    def _explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("the evaluator opened a StateStore")

    monkeypatch.setattr(store_module.StateStore, "__init__", _explode)

    from app.improvement.dataset import load_dataset
    from app.improvement.evaluator import evaluate_dataset

    dataset = load_dataset(
        PROJECT_ROOT / "improvement" / "dataset" / "content_eval_v1.json")
    artifact = evaluate_dataset(dataset, designation="baseline")

    assert artifact.case_count == len(dataset.cases)


def test_dataset_contexts_build_without_a_store():
    """A frozen case builds its real context through the offline stub.

    The stub reports no checkpoints and exposes no write or migration surface,
    so handing it to ``build_context`` cannot reach the authoritative store.
    """
    from app.improvement.dataset import _OfflineCheckpointStore
    from app.state.store import StateStore

    stub = _OfflineCheckpointStore()
    assert stub.list_checkpoints() == []
    assert not isinstance(stub, StateStore)
    for forbidden_attr in ("migrate", "apply_migrations", "connect", "write"):
        assert not hasattr(stub, forbidden_attr)
    # The builder is handed the stub and nothing else.
    source = (IMPROVEMENT_PACKAGE / "dataset.py").read_text(encoding="utf-8")
    assert "store=_OfflineCheckpointStore()" in source
