# Retrieval Learning Documentation

This directory documents the **retrieval milestone** of PersonalBrandingAgent
— not as a textbook, but as a record of what each technique does *on this
specific corpus* (`data/`, ~71 Markdown files, 342 chunks, embedded with
`all-MiniLM-L6-v2` into local Chroma).

## Start here

Run the comparison playground and read alongside these docs:

```bash
python -m app.ingestion.pipeline                      # data/ -> Chroma (once)
python -m app.retrieval.compare "What evidence supports my backend engineering skills?"
python -m app.retrieval.evaluation                    # gold-set metrics per strategy
```

## Documents

| Document | Concept |
|---|---|
| [semantic-vs-keyword.md](semantic-vs-keyword.md) | Vector retrieval vs BM25 — meaning vs exact terminology |
| [metadata-filtering.md](metadata-filtering.md) | Structured filters over path/heading-derived metadata |
| [multi-query.md](multi-query.md) | LLM query expansion (OpenRouter) + union/dedup |
| [hybrid-reranking.md](hybrid-reranking.md) | RRF fusion and cross-encoder reranking |
| [evaluation.md](evaluation.md) | Hit@K / MRR, and what the numbers actually showed |

## The six strategies in one table

| Strategy | Module | What it adds | Cost |
|---|---|---|---|
| `vector` | `app/retrieval/vector.py` | semantic matching | embed query (~1ms after model load) |
| `metadata` | `app/retrieval/metadata.py` | precision via filters | near-zero |
| `bm25` | `app/retrieval/bm25.py` | exact terminology | ~5ms/query |
| `multi_query` | `app/retrieval/multi_query.py` | vocabulary-gap coverage | 1 LLM call + N searches |
| `hybrid` | `app/retrieval/fusion.py` | agreement across rankings | vector + bm25 |
| `reranked` | `app/retrieval/reranker.py` | precision at the top | cross-encoder over pool (~seconds) |

All six share the `RetrievalResult` model (`app/retrieval/models.py`) and are
reachable through one facade:

```python
from app.retrieval.engine import RetrievalEngine
engine = RetrievalEngine()
result = engine.retrieve(query, strategy="hybrid", top_k=5)
```

## What we observed on this corpus (summary)

Observed during the milestone build, query
*"What evidence supports my backend engineering skills?"*:

- **vector ∩ BM25 overlap: 0 of 5** — the two strategies returned *completely
  different documents* for the same question. Neither is "better"; they see
  the corpus differently.
- **Hybrid promoted a chunk ranked vector=9, bm25=4 to #1** — RRF rewards
  cross-strategy agreement more than any single strong rank.
- **Reranking moved a chunk from fusion rank 5 to #1** — the cross-encoder
  read query and document together and disagreed with the bi-encoder.
- **BM25 missed the "certificates from IBM, Vanderbilt, Anthropic" gold
  query** — no exact term overlap; pure keyword search fails on
  provider-name phrasing.
- **Multi-query needs a valid OpenRouter key** — with the fallback, it
  degenerates to plain vector search.

Details and exact outputs: the linked documents.
