# Metadata-Aware Retrieval

## 1. What problem does this solve?

This corpus is not a pile of text — it's a **structured knowledge base**:

```text
evidence/backend/fastapi.md          category=evidence, domain=backend
evidence/ai/rag_learning.md          category=evidence, domain=ai
stories_lessons/quizey_idempotency.md  category=stories_lessons
certificates/educba_pymongo-advanced.md category=certificates
```

Each file also carries explicit headings with a controlled vocabulary
(`## Evidence state: VERIFIED`, `## Status: COMPLETED`) — see
`data/evidence/README.md`. A question like:

> "Show me **verified evidence** about backend engineering"

is not just a similarity question — it's a **constraint** question. Plain
vector search will happily return a `LEARNING`-state course note or an audit
file, because they're semantically adjacent. Metadata filtering restricts
the search space to documents that *provably are* what the user asked for.

## 2. What did normal vector search fail to do?

In the real comparison run for *"What evidence supports my backend
engineering skills?"*:

- **Unfiltered vector** top hit: `evidence/professional/professional.md`
  (distance 0.84) — semantically close, but *professional* evidence, and its
  actual FlyRank entry is marked UNVERIFIED. A generation step that consumed
  this as "backend evidence support" would be under-grounded.
- **Metadata-filtered** (`category=evidence, domain=backend`) top hit:
  `evidence/backend/fastapi.md` — exactly the slice of the corpus the
  question describes.

## 3. What changed in the retrieval pipeline?

Two things, both during **ingestion** (metadata must exist before it can
be filtered):

1. **Path-derived metadata** (`app/ingestion/loader.py`): top-level
   directory → `category`; `evidence/<subdir>` → `domain`. Reliable because
   the directory hierarchy *is* semantic (an explicit project decision — see
   ADR-003 in `docs/decisions/ADRs/README.md`).
2. **Heading-derived metadata** (`app/ingestion/metadata.py`): `## Evidence
   state` and `## Status` headings parsed against fixed vocabularies
   (VERIFIED/DOCUMENTED/IN_PROGRESS/LEARNING/ASPIRATIONAL/UNVERIFIED/STALE;
   COMPLETED/IN PROGRESS/…). Leading keyword only —
   `VERIFIED (repo exists)` → `VERIFIED`. Anything ambiguous stays **unset**
   rather than guessed.

At query time (`app/retrieval/metadata.py`), caller-provided filters become
a Chroma `where` clause:

```python
engine.retrieve(query, strategy="metadata",
                filters={"category": "evidence", "evidence_state": "VERIFIED"})
# -> where: {"$and": [{"category": {"$eq": "evidence"}},
#                     {"evidence_state": {"$eq": "VERIFIED"}}]}
```

Semantic search then runs *inside* that slice. Explicitly NOT an LLM deciding
filters — the first implementation is deterministic, and the playground's
`derive_filter()` (keyword → filter mapping) is documented as a heuristic.

## 4. When would I actually use it?

Always, in this project. The whole architecture's grounding principle
(evidence over plausibility — `docs/architecture/system-overview.md`) needs
the retrieval layer to answer "what *category* of support does this claim
have?" Metadata is what lets a future Agent say: *this story is a nice
narrative but the evidence file is UNVERIFIED, so soften the claim.*

## 5. What does it cost?

- Ingestion: a few regexes per file (negligible).
- Query: near-zero (18ms measured in evaluation — *faster* than unfiltered
  vector, because the filtered corpus slice is smaller).
- The real cost is **corpus discipline**: metadata only exists because the
  files follow conventions. A file without `## Evidence state` silently
  has no evidence_state — filtering excludes it. That's correct-by-design
  (don't guess) but means new files must follow the conventions.

## 6. What can go wrong?

- **Over-filtering** to an empty result set (the playground shows
  "(no documents returned)"). The filter vocabulary must match the corpus's
  actual values exactly — `IN-PROGRESS` vs `IN PROGRESS` matters
  (we normalize to `IN PROGRESS`).
- **Unknown filter keys fail loudly** (`ValueError`) rather than being
  silently ignored — a typo like `evidenceState` raises instead of returning
  unfiltered results.
- **Filters are exact-match**: no "backend OR devops", no ranges. `$or` /
  `$in` support is trivial to add when needed (Chroma supports them).

## 7. What did we observe in this repository?

- Metadata Hit@5 = 1.00, MRR = 1.000 on the gold set — but note the
  playground-derived filters were generous (`category=evidence`).
- Latency dropped vs unfiltered vector (18ms vs ~355ms) — the filter does
  real work before embedding search runs.

Try:

```bash
python -m app.retrieval.compare "Show me verified evidence about backend"
```

and watch the METADATA section return only
`evidence_state=VERIFIED` chunks, while VECTOR returns whatever is
semantically closest regardless of evidential weight.
