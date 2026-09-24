"""Shared pytest fixtures: tiny fakes for embeddings / reranking / LLM.

None of these touch the network, so the whole suite runs offline.

The synchronization fixtures build throwaway git repositories under
``tmp_path``. They must never point at a real workspace: ``PLAN.md`` Step 3
requires the tests to use temporary repositories, and a test that ran against
``~/LLMs`` would be testing the user's machine rather than the code.
"""
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app import paths as app_paths
from app.sources.enums import SourceType
from app.sources.models import ExcludeRule, SourceDefinition
from app.state.enums import LifecycleState
from app.state.store import StateStore

#: The production locations no test may touch. Captured here, once, from the
#: production configuration itself — never hardcoded — so the guard below
#: tracks the real paths even if configuration changes them.
PRODUCTION_DB_PATH = Path(app_paths.STATE_DB_PATH)
PRODUCTION_CHROMA_DIR = Path(app_paths.CHROMA_DIR)

# Make "import app" / "import tests" work regardless of CWD.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeEmbeddings:
    """Deterministic fake embedding function.

    Embeds a string as a fixed-dim vector where each token adds 1.0 to a
    bucket derived from a STABLE digest (md5) of the token — unlike
    built-in hash(), which is randomized per process (PYTHONHASHSEED) and
    would make test outcomes flaky. Texts sharing tokens land close
    together in cosine space, which is all the retrieval tests need.
    """

    dim = 64

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        import hashlib
        vec = [0.0] * self.dim
        for token in set(text.lower().split()):
            digest = hashlib.md5(token.encode()).digest()
            bucket = digest[0] % self.dim
            vec[bucket] += 1.0
        return vec


class FakeCrossEncoder:
    """Deterministic fake reranker: scores (query, doc) pair overlap.

    Returns a higher score the more query terms appear in the document —
    mimicking 'relevance' well enough to test the reranking pipeline.
    """

    #: What the reranked diagnostics record as the scoring model.
    model_name = "fake-cross-encoder"

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores = []
        for query, doc in pairs:
            q_terms = set(query.lower().split())
            d_terms = set(doc.lower().split())
            scores.append(float(len(q_terms & d_terms)))
        return scores

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """The name :class:`RerankedRetriever` calls. Same fake, both seams."""
        return self.predict(pairs)


@pytest.fixture
def fake_embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def fake_cross_encoder() -> FakeCrossEncoder:
    return FakeCrossEncoder()


# ------------------------------------------------- Step 3: synchronization ---

def git(repo: Path, *args: str) -> str:
    """Run one git command in a test repository and return its stdout."""
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=str(repo), check=True, capture_output=True, text=True,
    )
    return completed.stdout


@dataclass
class TempRepo:
    """A throwaway git repository, committed to as the test needs."""

    path: Path
    _commits: int = field(default=0)

    def write(self, relative: str, text: str) -> Path:
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def remove(self, relative: str) -> None:
        (self.path / relative).unlink()

    def move(self, source: str, target: str) -> None:
        git(self.path, "mv", source, target)

    def commit(self, message: str = "change") -> str:
        """Stage everything and commit. Returns the commit id."""
        git(self.path, "add", "-A")
        git(self.path, "commit", "--quiet", "-m", message)
        self._commits += 1
        return self.head()

    def head(self) -> str:
        return git(self.path, "rev-parse", "HEAD").strip()


@pytest.fixture
def make_git_repo(tmp_path):
    """Factory for temporary git repositories, isolated per test."""
    created = 0

    def _make(name: str = "repo", branch: str = "main") -> TempRepo:
        nonlocal created
        created += 1
        path = tmp_path / f"{name}-{created}"
        path.mkdir(parents=True)
        git(path, "init", "--quiet", f"--initial-branch={branch}")
        git(path, "config", "user.email", "test@example.invalid")
        git(path, "config", "user.name", "Sync Test")
        git(path, "config", "commit.gpgsign", "false")
        return TempRepo(path=path)

    return _make


@pytest.fixture
def make_source(tmp_path):
    """Factory for source definitions pointing at a test directory."""
    def _make(path, *, name: str = "test-source", type: SourceType = SourceType.GIT,
              include: tuple[str, ...] = ("**/*.md", "**/*.py"),
              exclude: tuple[tuple[str, str], ...] = (),
              lifecycle: LifecycleState = LifecycleState.ACTIVE,
              ref: str | None = "main") -> SourceDefinition:
        return SourceDefinition(
            name=name,
            type=type,
            local_path=Path(path),
            lifecycle=lifecycle,
            include=include,
            exclude=tuple(ExcludeRule(pattern=p, reason=r) for p, r in exclude),
            ref=ref if type is SourceType.GIT else None,
            description="a temporary source for tests",
        )

    return _make


@pytest.fixture
def state_store(tmp_path) -> StateStore:
    """A real operational store in a temporary file, closed after the test."""
    store = StateStore(tmp_path / "state" / "operational_state.db")
    yield store
    store.close()


@pytest.fixture
def chroma_store(tmp_path, fake_embeddings):
    """A temporary Chroma collection, separate from the project's own."""
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=f"sync_{tmp_path.name.replace('.', '_')}",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )


class RecordingIngest:
    """A stand-in for the ingestion pipeline that records what it was asked.

    Lets a test assert the *absence* of work — a no-change sync must not embed,
    must not write to Chroma, and must not even call this.
    """

    def __init__(self, result: dict | None = None, raises: Exception | None = None):
        self.calls: list[dict] = []
        self.result = result if result is not None else {"files_added": 0}
        self.raises = raises

    def __call__(self, *, candidates, purge, scope, embeddings=None, chroma=None):
        self.calls.append(
            {
                "candidates": tuple(c.relative_path for c in candidates),
                "purge": tuple(purge),
                "scope": scope,
            }
        )
        if self.raises is not None:
            raise self.raises
        return dict(self.result)

    @property
    def called(self) -> bool:
        return bool(self.calls)

    @property
    def last(self) -> dict:
        return self.calls[-1]


@pytest.fixture
def recording_ingest() -> RecordingIngest:
    return RecordingIngest()


# ------------------------------------------- operational-state isolation ---

def _abspath(path) -> str:
    import os

    return os.path.abspath(os.path.expanduser(str(path)))


@pytest.fixture(scope="session", autouse=True)
def isolated_operational_state(tmp_path_factory):
    """The suite-wide isolation boundary: tests can never reach production.

    Three layers, all explicit in this one place:

    1. *Redirect.* ``app.state.store.STATE_DB_PATH`` — the default
       ``StateStore()`` resolves — points at a session-temporary database.
       Lazy production opens (``build_context`` without a store, default
       retrieval engines) land here: readable, writable, migrated, and
       thrown away. ``app.paths`` (production configuration) is untouched.
    2. *Hard failure.* Any ``StateStore`` resolved to the real production
       path, or any Chroma collection persisted under the real production
       directory, raises ``AssertionError`` instead of opening. Accidental
       production access fails the test; it is never silent.
    3. *No egress.* Outbound sockets raise. Transports are faked throughout
       the suite (smtplib, LinkedIn get/post, LLMs); a test that needs the
       network does not exist, and one appearing later fails here first.

    Layer 1 preserves current behavior (187 default opens keep working);
    layers 2 and 3 are what make the invariant a property rather than luck.
    """
    import socket

    import app.state.store as store_module

    isolated_db = (
        tmp_path_factory.mktemp("isolated-state") / "operational_state.db"
    )
    original_db_path = store_module.STATE_DB_PATH
    store_module.STATE_DB_PATH = isolated_db

    original_init = store_module.StateStore.__init__

    def guarded_init(self, path=None):
        resolved = _abspath(path) if path is not None else _abspath(
            store_module.STATE_DB_PATH)
        if resolved == _abspath(PRODUCTION_DB_PATH):
            raise AssertionError(
                "test attempted to open the production state database at "
                f"{resolved}; pass an explicit temporary store instead"
            )
        return original_init(self, path)

    store_module.StateStore.__init__ = guarded_init

    chroma_guarded = False
    original_chroma_init = None
    try:
        from langchain_chroma import Chroma

        original_chroma_init = Chroma.__init__

        def guarded_chroma_init(self, *args, **kwargs):
            persist = kwargs.get(
                "persist_directory", args[1] if len(args) > 1 else None)
            if persist is not None and _abspath(persist) == _abspath(
                    PRODUCTION_CHROMA_DIR):
                raise AssertionError(
                    "test attempted to open the production Chroma "
                    f"collection at {persist}; pass an explicit temporary "
                    "store instead"
                )
            return original_chroma_init(self, *args, **kwargs)

        Chroma.__init__ = guarded_chroma_init
        chroma_guarded = True
    except ImportError:
        pass

    original_connect = socket.socket.connect

    def blocked_connect(self, *args, **kwargs):
        raise AssertionError(
            "network egress is blocked in tests; use the fakes "
            "(smtplib, LinkedIn get/post, LLMs) like the rest of the suite"
        )

    socket.socket.connect = blocked_connect

    try:
        yield {
            "production_db": PRODUCTION_DB_PATH,
            "production_chroma": PRODUCTION_CHROMA_DIR,
            "isolated_db": isolated_db,
        }
    finally:
        store_module.STATE_DB_PATH = original_db_path
        store_module.StateStore.__init__ = original_init
        if chroma_guarded:
            from langchain_chroma import Chroma

            Chroma.__init__ = original_chroma_init
        socket.socket.connect = original_connect
