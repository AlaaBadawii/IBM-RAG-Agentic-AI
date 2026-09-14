"""Shared pytest fixtures: tiny fakes for embeddings / reranking / LLM.

None of these touch the network, so the whole suite runs offline.
"""
import sys
from pathlib import Path

import pytest

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

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores = []
        for query, doc in pairs:
            q_terms = set(query.lower().split())
            d_terms = set(doc.lower().split())
            scores.append(float(len(q_terms & d_terms)))
        return scores


@pytest.fixture
def fake_embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def fake_cross_encoder() -> FakeCrossEncoder:
    return FakeCrossEncoder()
