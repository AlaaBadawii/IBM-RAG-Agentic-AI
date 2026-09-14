# Hybrid Retrieval (RRF) and Cross-Encoder Reranking

Two techniques that compose: fusion merges candidate lists; reranking
re-scores the survivors.

## Part A — Reciprocal Rank Fusion

### 1. What problem does this solve?

Vector and BM25 return *rankings* with incommensurable scores:

```text
vector: cosine distance  [0, ~2]   lower = better
bm25:   lexical score    [0, ∞)    higher = better
```

Averaging them is meaningless — the BM25 number is bigger, so it would win
by *units*, not by evidence. RRF sidesteps units entirely by using only
**ranks**:

```text
RRF(d) = Σ over each ranking list containing d of  1 / (rank_d + k)
```

implemented explicitly in `app/retrieval/fusion.py::rrf_score` (k=60, the
standard value from Cormack et al. 2009, configurable via `RRF_K`).

### 2. What did normal vector search fail to do?

For "What evidence supports my backend engineering skills?":

- vector top-1: `evidence/professional/professional.md` (semantic, but
  professionally-oriented evidence)
- bm25 top-1: `certificates/manara_node-js-backend-development-program.md`
  (literal "backend" match)
- **neither top-1 was the corpus's strongest backend-evidence document.**

The hybrid result promoted `certificates/alx_backend-software-engineer.md`
— vector rank **9**, BM25 rank **4** — to overall **#1**, because it was
the chunk *both* strategies independently agreed on. The vector-only #1
(never ranked by BM25) fell to #3. RRF rewards **agreement between
independent evidence sources**, which is a better relevance signal than
either source alone.

### 3. What changed in the retrieval pipeline?

`HybridRetriever.retrieve()`:

```text
vector candidates (10)   bm25 candidates (10)
        \                    /
         RRF: score each unique chunk
              by sum of 1/(rank+60) over lists containing it
                -> fused ranking -> top_k
```

Both candidate lists come from the *same* Chroma corpus (BM25 is indexed
over Chroma's stored chunks), so `chunk_id` matching is exact. Every fused
result carries its provenance in metadata — `vector_rank`, `bm25_rank`,
`rrf_contributions` — so the playground can explain each promotion.

### 4. When / costs / failure modes

- Use: default "best effort" strategy when you don't know whether the query
  is conceptual or terminological.
- Cost: one vector search + one BM25 pass (~28ms measured).
- Failure: k too small → the #1 spot of one list dominates; k too large →
  rankings flatten toward tie-breaks. The unit test
  `test_rrf_k_damps_top_ranks` demonstrates the damping tradeoff.
- RRF is deliberately blind to *scores* — a chunk at BM25 rank 1 with score
  50 and one with score 0.5 contribute identically. That robustness is
  also a blindness.

## Part B — Cross-Encoder Reranking

### 1. What problem does this solve?

The embedding model is a **bi-encoder**: query and document are embedded
*independently*, then compared with one dot product. They never "see" each
other. A **cross-encoder** concatenates query and document, passes the pair
through one transformer, and outputs a relevance score — it can attend
across the query and the document tokens and judge their *interaction*.

That precision is expensive: one forward pass per (query, document) **pair**.
Rerunning it over 342 chunks would mean 342 forward passes per query. So we
split the pipeline:

```text
retrieval  = HIGH RECALL, cheap per document, runs over everything
reranking  = HIGH PRECISION, expensive per pair, runs over ~20 survivors
```

`app/retrieval/reranker.py`:

```text
vector + BM25 -> RRF fused candidate pool (20)
    -> cross-encoder/ms-marco-MiniLM-L-6-v2 scores each (query, chunk)
    -> reranked top 5
```

### 2. What did we observe in this repository?

Reranked run for *"What did I learn about Kubernetes deployments?"*:

```text
1. evidence/devops/devops.md                 ce=5.17  pre-rerank rank 3
2. stories_lessons/kubernetes_first_step_typos.md  ce=4.92  pre-rerank rank 5
3. stories_lessons/kubernetes_first_step_typos.md  ce=3.89  pre-rerank rank 2
```

The cross-encoder *disagreed* with RRF: rank-3 → #1, rank-2 → #3. Reading
the chunks confirms the reranker's judgment — the devops.md chunk is the
denser answer to the question; the rank-2 chunk was a different section of
the same story file.

Honest negative result from the gold-set evaluation: reranked **MRR 0.896
< vector 1.000**. Reranking can *hurt* when the candidate pool ordering was
already good, or when the cross-encoder's notion of relevance (trained on
MS MARCO web queries) mismatches this corpus's notion (personal KB files).
This is exactly the kind of thing evaluation exists to reveal — precision
techniques are not free wins.

### 3. When / costs / failure modes

- Use: final precision pass when feeding a generator (top-5 quality
  matters more than top-20 recall), and latency budget allows.
- Cost: ~6–8 seconds for 20 pairs on CPU (measured; model load ~2s cached).
  GPU would change this completely.
- Failure modes: domain mismatch of the cross-encoder; reranking a pool
  that already excluded the right documents (reranking cannot recover recall —
  it only reorders what retrieval found); truncation of long chunks to the
  encoder's max length (512 tokens for ms-marco-MiniLM) silently ignoring
  chunk tails.

### 4. What can go wrong that we handled explicitly?

- Only the candidate pool is reranked — never the whole corpus (by design,
  see `RerankedRetriever.retrieve(candidate_pool=20)`).
- `pre_rerank_rank` is kept in each result's metadata, and
  `rank_changes` in diagnostics, so every promotion/demotion is visible in
  the playground output.
