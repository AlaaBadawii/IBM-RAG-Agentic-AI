# Multi-Query Retrieval

## 1. What problem does this solve?

The **vocabulary gap** between how a person asks and how the knowledge base
phrases the same fact:

```text
Question:   "What evidence supports my backend engineering skills?"
Corpus:     "FastAPI shipment API", "SQLAlchemy models", "Alembic migrations",
            "layered architecture", "REST endpoints"
```

One embedding of the original question lands somewhere in the middle of
these concepts; the chunks that would best answer it might each be closer
to *their own* phrasing than to the question's phrasing. Multi-query
retrieval attacks this by **expanding the query**:

```text
original question
    -> LLM generates N alternative phrasings
    -> vector retrieval for EACH phrasing
    -> union, deduplicated by chunk id
    -> ranked by best rank achieved in any query
```

## 2. What did normal vector search fail to do?

Nothing dramatic on this corpus (our gold queries are already
corpus-flavored, so plain vector scores Hit@5 = 1.00). The failure mode
appears when the questioner's vocabulary diverges from the corpus — the
case a real LinkedIn-content agent will face constantly, since post topics
("reliability", "shipping fast", "production mindset") won't literally match
KB vocabulary ("idempotency keys", "state machine", "containerized CI").

## 3. What changed in the retrieval pipeline?

`app/retrieval/multi_query.py`:

- **LLM call through OpenRouter** (`langchain_openai.ChatOpenAI` with
  `base_url=https://openrouter.ai/api/v1`, model from `config.MODEL_ID`,
  temperature 0 — query rewriting wants determinism). The prompt asks for
  N one-line rewrites; the count is configurable (`MULTI_QUERY_COUNT`, default 4).
- **The original query is always preserved** — rewrites supplement, never
  replace.
- **Deduplication by chunk id**: the same chunk retrieved by multiple
  phrasings appears once, keeping its *best* rank (`by_chunk` dict keyed on
  `chunk_id`).
- **Deterministic fallback**: if the OpenRouter call fails (401, network,
  no key), the strategy degrades to `[original query]` — still functional,
  flagged as `llm_fallback_used: True` in diagnostics.

## 4. When would I actually use it?

- User-facing search where you can't predict phrasing.
- When recall matters more than latency (1 LLM call + N searches ≈ hundreds
  of ms).
- NOT for precise, terminology-exact queries ("PyMongo") — expansion adds
  nothing there and adds noise. This is why it's an *explicit strategy* in
  the engine, not a default layer: `engine.retrieve(q, strategy="multi_query")`.

## 5. What does it cost?

One OpenRouter API call (~150–500ms, fractions of a cent) plus N vector
searches. Against purely-local strategies it's the only one with a marginal
monetary cost.

## 6. What can go wrong?

- **Bad rewrites** pollute the union with off-topic chunks. The rank-based
  merge mitigates this (an off-topic chunk retrieved by one rewrite at rank 5
  competes with on-topic chunks at rank 1–2 from other queries).
- **Drift**: the LLM can subtly change the *intent* of the question. The
  original query always participates, so drift never fully replaces intent.
- **Key issues**: in this repository's current state, `.env`'s
  `OPENAI_API_KEY` holds an OpenAI (sk-proj-) key, not an OpenRouter key
  (verified: OpenRouter's `/api/v1/key` endpoint returns 401 "User not
  found"). Until a valid OpenRouter key is set, every multi-query run uses
  the fallback. This is a config fix, not a code issue — the fake-LLM test
  (`tests/test_fusion.py::test_multi_query_expands_and_dedupes`) proves the
  expansion logic, and the 401 proved the fallback path.

## 7. What did we observe in this repository?

With the fallback active, multi_query scored identically to vector
(Hit@5 1.00, MRR 1.000) — as expected, since fallback = original query only,
plus ~170ms of wasted API attempt. The strategy's real value on this corpus
is untested until the key is fixed; the honest evaluation note in
`evaluation.md` records exactly this.

To verify the expansion once a key is set:

```bash
python -m app.retrieval.compare "How do I make systems dependable?"
```

The MULTI-QUERY section will list the generated queries in diagnostics, and
the WHY section will explain that the union caught chunks a single phrasing
missed.
