# Retrieval Evaluation

## 1. What problem does this solve?

Without measurement, "hybrid feels better" is vibes. The gold-set evaluation
(`python -m app.retrieval.evaluation`) answers: *for these questions, on
this corpus, which strategy actually surfaced the right documents, and how
high did it rank them?*

## 2. The gold set

`tests/gold_queries.json` — 12 queries drawn from the real corpus, each with
the source files a good retrieval should surface. Deliberately varied:

- **semantic**: "What is my preferred LinkedIn writing style and tone?"
- **exact terminology**: "Quizey attempt state machine"
- **evidence-focused**: "What evidence supports my database experience with PyMongo and MongoDB?"
- **project-focused**: "Which projects demonstrate that I can build AI agents from scratch without frameworks?"
- **story/lesson-focused**: "Why should I never trust an LLM's arithmetic?"
- **metadata-filterable**: "Show me verified evidence…" (playground)
- **broad**: "What am I currently learning about RAG and agentic AI?"

A "hit" is at the **source-file level** (any chunk from a relevant file
counts), because the gold set is defined per file.

## 3. Metrics

- **Hit@K** — did ANY relevant source appear in the top K? Recall-oriented.
  Coarse: one lucky chunk at rank 5 scores the same as a perfect answer.
- **MRR** (mean reciprocal rank) — `1 / rank` of the first relevant
  document, averaged over queries. Precision-at-the-top oriented: a
  relevant doc at rank 1 scores 1.0, at rank 3 scores 0.33.

Also reported: average latency, average result count, and multi-query
fallback count (queries where the LLM was unavailable).

## 4. Results (real run, 2026-09-08, 342 chunks)

```text
strategy       Hit@5     MRR    avg_ms  fallbacks
-------------------------------------------------
vector          1.00   1.000     354.6          0
metadata        1.00   1.000      18.1          0
bm25            0.92   0.736       4.7          0
multi_query     1.00   1.000     174.3         12
hybrid          1.00   0.938      28.2          0
reranked        1.00   0.896    8176.4          0
```

## 5. What the numbers actually say

These are NOT impressive numbers, and reading them honestly is the point:

1. **The gold set is too easy.** Hit@5 = 1.00 for vector means the queries
   are phrased too much like the corpus. A harder set (paraphrased, wrong
   vocabulary, adversarial) would differentiate strategies. The multi-query
   doc explains why that's exactly the case multi-query targets.
2. **BM25's 0.92 / 0.736 is real signal**: the miss was *"What certificates
   have I earned from IBM, Vanderbilt, and Anthropic?"* — no exact term
   overlap, so lexical search fails. BM25's MRR is lower because when it
   does hit, it tends to rank secondary mentions above the primary file.
3. **multi_query = vector is an artifact**: 12/12 fallbacks (no valid
   OpenRouter key in `.env` at run time), so multi_query degenerated to
   plain vector search. The row currently measures the fallback, not the
   technique.
4. **reranked MRR < vector MRR is a true negative result**: the
   ms-marco cross-encoder reordered an already-good ranking and made the
   top hit worse on 1+ queries. Precision techniques are not free wins;
   they must earn their latency cost on a *harder* gold set.
5. **Latency ordering** (metadata 18ms < bm25 5ms… wait, bm25 is fastest;
   metadata 18ms includes filter construction) — the real takeaway is
   reranked costs ~8 seconds on CPU for 20 pairs, ~300× hybrid. That's
   the recall/precision tradeoff made concrete.

## 6. How to make the evaluation harder (next iteration)

- Add paraphrase queries that don't share vocabulary with the corpus.
- Add queries with NO relevant documents (measures noise/false positives).
- Report Recall@K (all relevant sources found, not just one) alongside Hit@K.
- Re-run after setting a valid OpenRouter key so multi_query measures the
  technique rather than the fallback.
- Consider nDCG if graded relevance is ever introduced (this corpus's
  evidence hierarchy — VERIFIED > DOCUMENTED > … — could *become* the
  grading, which is a nice future convergence with the project's
  evidence-policy goals).

## 7. What can go wrong with these metrics themselves?

- **Gold-set leakage**: queries copied from corpus headings measure string
  matching, not retrieval.
- **Source-level hits hide chunk-level errors**: the right *file* at rank 2
  via its wrong *chunk* still counts as a hit.
- **12 queries is small**: single-query swings move MRR by ±0.08. Treat
  differences under ~0.1 as noise on this set.
