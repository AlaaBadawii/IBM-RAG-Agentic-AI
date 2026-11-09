# Job Description Matcher — Semantic Search with ChromaDB

**Status: Plan only — no Python implementation or job dataset is tracked.**

[Course 3](../README.md) · [Certificate](../../README.md)

A proposed Python application for job-description search with **ChromaDB** and
**SentenceTransformers**. This README preserves the intended design and retrieval
concepts; it does not describe completed functionality.

This project is part of **Course 3 — Vector Databases for RAG: An Introduction** (IBM RAG and Agentic AI Professional Certificate). It follows the IBM lab progression from document storage through similarity search with metadata filtering and evaluation.

---

## 1. Intended Functionality (Not Implemented)

1. Store a proposed dataset of ~30 job descriptions with rich metadata.
2. Generate embeddings using `all-MiniLM-L6-v2`.
3. Search natural-language queries and combine results with category/location filters.
4. Evaluate retrieval with Hit@K and Precision@K.

None of these components or evaluation results exists in the tracked project yet.

### Core philosophy

> "You're not just learning: 'Chroma returns similar documents.' You're learning: 'What does my embedding model consider semantically similar?'"

---

## 2. Proposed Design

### Data model

Each proposed job record would have these fields:

| Field | Purpose |
|---|---|
| `id` | Unique identifier (e.g., `job_001`) |
| `title` | Job title |
| `company` | Company name |
| `location` | Job location (city or "Remote") |
| `category` | Broad technical category |
| `description` | Full job description text |

**Searchable text vs. metadata** — this is a critical distinction:

- **Searchable text** (`documents` in Chroma): the free-text description that gets embedded. Typically combines title + description for optimal semantic matching.
- **Metadata** (`metadatas` in Chroma): structured fields used for filtering, not semantic matching.

```python
# What gets embedded (searchable text):
"Build REST APIs using Python, FastAPI and PostgreSQL..."

# What gets stored as metadata (for filtering):
{"title": "Backend Software Engineer", "company": "TechCorp", "location": "Cairo", "category": "Backend"}
```

### Search flow

```
User query → Chroma collection.query() → top-K results with distances and metadata
```

Chroma's `collection.query()` accepts `query_texts`, `n_results`, `where` (metadata filters), and returns IDs, documents, metadatas, and distances.

---

## 3. Actual Tracked Contents

```
job_description_matcher/
├── README.md           # Proposed design and current status
├── requirements.txt
└── plan.md            # Detailed 12-task implementation plan
```

[`plan.md`](plan.md) is the implementation roadmap. The proposed configuration,
dataset, vector store, search service, CLI, and evaluation still need to be built.

---

## 4. Proposed Configuration (Not Consumed by Code)

| Constant | Value | Purpose |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | `"all-MiniLM-L6-v2"` | 384-dim embeddings, trained on 1B sentence pairs |
| `COLLECTION_NAME` | `"jobs"` | Chroma collection name |
| `PERSISTENCE_DIRECTORY` | `"./data/chroma"` | Persistent storage (survives restarts) |
| `DEFAULT_NUM_RESULTS` | `5` | Default number of results to return |
| `DISTANCE_METRIC` | `"cosine"` | Cosine distance (0 identical, 1 orthogonal, 2 opposite) |

---

## 5. Dependencies and Execution State

[`requirements.txt`](requirements.txt) lists dependencies for the proposed
implementation. Installing them does not create an application. No entry point,
environment-variable reader, ingestion command, test suite, or dataset is tracked.

---

## 6. Remaining Implementation Work

- Supply the job dataset and validate searchable text and metadata.
- Implement collection creation, ingestion, search, and metadata filtering.
- Build a real command-line interface before documenting usage commands.
- Add labeled queries, metric calculations, and assertion-based tests.
- Consider an optional LLM summary only after retrieval is implemented.

The previously described `cli.py` commands are unavailable because that file does not exist.

---

## 7. Planned features

| Phase | Description |
|---|---|
| **Evaluation** | Define ~10 test queries with expected relevant jobs; calculate Hit@3, Hit@5, Precision@3 |
| **Search experimentation** | Run 10 queries, record results, analyze surprising/bad matches, write "What I Learned About Embeddings" |
| **Architecture refactor** | Separate concerns into `search.py` → `vector_store.py` → Chroma; add type hints, docstrings, exception handling |
| **Optional LLM phase** | Use LangChain LCEL to generate a natural-language summary of the best-matching jobs (RAG-lite) |

---

## 8. ChromaDB key concepts

| Concept | Description |
|---|---|
| Collection | Logical grouping of documents (like a table) |
| Document | A piece of text + metadata (what gets embedded) |
| ID | Unique identifier for each document |
| Metadata | Structured key-value pairs for filtering |
| Distance metric | How similarity is measured (cosine, euclidean, dot) |

---

## 9. Semantic search best practices

1. **Combine title + description** for the searchable text — this ensures the job title influences semantic similarity while the description provides detail.
2. **Use metadata for filtering**, not semantic similarity — metadata filters narrow the search space while semantic search ranks by similarity.
3. **Check the configured distance metric** — lower is better for distance, but range and interpretation depend on the metric. Cosine distance can range from 0 to 2; the model does not choose the Chroma collection metric.
4. **Different models behave differently** — try `all-MiniLM-L12-v2` or `MPNet` for comparison.
5. **Metadata filtering + semantic search** = most powerful combination — "Find AI jobs in Cairo" works best with both.

---

## 10. Evaluation metrics reference

| Metric | Definition | Interpretation |
|---|---|---|
| **Hit@K** | Expected job in top K results | Percentage of queries where at least one expected job appears |
| **Precision@K** | (Relevant in top K) / K | Of top K, what fraction are relevant |
| **Recall@K** | (Relevant in top K) / (Total relevant) | Of all relevant, what fraction appear in top K |
