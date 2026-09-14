# Semantic vs Keyword Retrieval

Two ways to find "relevant" — demonstrated on the PersonalBrandingAgent corpus.

## 1. What problem does each solve?

**Vector retrieval** (`app/retrieval/vector.py`):
> "What did I learn about backend architecture?" should find a chunk that
> says *"layered a FastAPI service with SQLAlchemy models"* — even though
> zero words repeat.

It works by embedding the query and every chunk into the same vector space
(`all-MiniLM-L6-v2`, 384 dims) and ranking by cosine similarity. The
embedding model was trained on enough text that "backend architecture" and
"layered FastAPI service" land near each other.

**BM25** (`app/retrieval/bm25.py`):
> "PyMongo" should find the chunks that literally contain "PyMongo" — and
> rank them by how *rare* that term is in the corpus and how often it
> appears in the chunk.

BM25 is a lexical scoring function: term frequency × inverse document
frequency × document-length normalization. No neural model, no meaning —
just statistics over exact tokens.

## 2. What does plain vector search fail to do?

- **Exact terminology.** A query for a specific tool name (`Alembic`,
  `PyMongo`, `Jenkins`) can be diluted by semantically-nearby but wrong
  chunks. In our comparison run for "What evidence supports my backend
  engineering skills?", the top vector hit was
  `evidence/professional/professional.md` — semantically adjacent
  (professional evidence) but not the backend evidence the question asks for.
- **Rare tokens.** MiniLM compresses 384-dim meaning from whole sentences;
  a single rare token contributes little to the embedding direction.

## 3. What does BM25 fail to do?

- **Vocabulary gap.** The gold query *"What certificates have I earned from
  IBM, Vanderbilt, and Anthropic?"* scored Hit@5 = 0 for BM25 but 1.00 for
  vector: the certificate files discuss "course topics", "completed
  learning", provider names appear in headings/table rows that tokenize
  away from the query's phrasing. No exact term match, no BM25 result.
- **Paraphrase.** "database experience" vs "MongoDB CRUD service" shares no
  tokens.

## 4. What changed in the retrieval pipeline?

Nothing extra — BM25 indexes the *same* chunks Chroma stores
(`BM25Retriever._build_index()` pulls all documents/metadata from Chroma via
`store.get()`). Both strategies always rank the same universe of documents,
which is exactly what makes fusion (see [hybrid-reranking.md](hybrid-reranking.md))
meaningful.

Our tokenizer is deliberately visible in `app/retrieval/bm25.py`:

```python
def tokenize(text): return re.findall(r"[a-z0-9]+", text.lower())
```

No stemming, no stopwords — "deployments" ≠ "deployment". A real production
system would reconsider this; here the simplicity is the lesson: tokenization
IS the load-bearing decision in lexical retrieval.

## 5. When would I actually use each?

| Situation | Use |
|---|---|
| User asks conceptually ("how do I think about API design?") | vector |
| User names a specific tool/file/project ("Alembic", "quizey_v2") | BM25 |
| Both (normal case) | hybrid — see [hybrid-reranking.md](hybrid-reranking.md) |

## 6. What does it cost?

- Vector: embed the query once (~1ms after the model loads; model load
  ~1s, cached). Measured avg latency: ~355ms including first-load amortization.
- BM25: builds an index over 342 chunks once (~50ms), then ~5ms/query.
  No API cost, fully local.

## 7. What can go wrong?

- BM25 scores can be **negative** for terms that appear in nearly every
  document (IDF goes negative when a term is corpus-wide). We hit this in
  tests with a tiny corpus — see the note in `bm25.py` `_rank_scores()`.
- **Scores are not comparable across strategies**: cosine distance is
  "lower is better" in [0, ~2]; BM25 is "higher is better" and unbounded.
  The playground prints score semantics per strategy for this reason.
  Never average a cosine distance with a BM25 score — that's why RRF exists.

## 8. What did we observe in this repository?

For the comparison query, **vector and BM25 overlapped on 0 of 5 top
documents** — two genuinely different views of relevance. Try:

```bash
python -m app.retrieval.compare "PyMongo"
python -m app.retrieval.compare "How should I think about database design?"
```

The first query favors BM25 (exact tool name); the second favors vector
(conceptual). The playground's WHY section shows the exact shared tokens
behind each BM25 hit.
