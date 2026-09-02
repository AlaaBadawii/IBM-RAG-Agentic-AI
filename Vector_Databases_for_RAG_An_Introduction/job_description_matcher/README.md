# Job Description Matcher — Semantic Search with ChromaDB

A Python application that stores job descriptions in **ChromaDB**, generates embeddings using **SentenceTransformers**, and enables natural-language semantic search with metadata filtering and evaluation.

This project is part of **Course 3 — Vector Databases for RAG: An Introduction** (IBM RAG and Agentic AI Professional Certificate). It follows the IBM lab progression from document storage through similarity search with metadata filtering and evaluation.

---

## 1. What this project does

1. **Stores** ~30 job descriptions in ChromaDB with rich metadata (title, company, location, category, description)
2. **Generates** embeddings using `all-MiniLM-L6-v2` (SentenceTransformers)
3. **Enables** natural-language semantic search with similarity scoring
4. **Provides** metadata filtering (category, location) combined with semantic search
5. **Supports** experimentation and evaluation metrics (Hit@K, Precision@K)

### Core philosophy

> "You're not just learning: 'Chroma returns similar documents.' You're learning: 'What does my embedding model consider semantically similar?'"

---

## 2. How it works

### Data model

Each job record has these fields:

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

## 3. Project structure

```
job_description_matcher/
├── config.py          # Configuration constants (embedding model, Chroma settings)
├── data.py            # Job dataset (~30 records across 8 categories)
├── vector_store.py    # ChromaDB operations (ingest, query)
├── search.py          # Semantic search logic (with metadata filtering)
├── cli.py             # Command-line interface (ingest, search)
├── requirements.txt
├── .gitignore
├── .env.example
└── plan.md            # Detailed 12-task implementation plan
```

---

## 4. Key configuration

| Constant | Value | Purpose |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | `"all-MiniLM-L6-v2"` | 384-dim embeddings, trained on 1B sentence pairs |
| `COLLECTION_NAME` | `"jobs"` | Chroma collection name |
| `PERSISTENCE_DIRECTORY` | `"./data/chroma"` | Persistent storage (survives restarts) |
| `DEFAULT_NUM_RESULTS` | `5` | Default number of results to return |
| `DISTANCE_METRIC` | `"cosine"` | Cosine distance (0 = identical, 1 = opposite) |

---

## 5. Setup

**Requirements:** Python 3.10+, internet access for downloading the embedding model on first run.

```bash
cd job_description_matcher
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt`:
```
chromadb
sentence-transformers
torch
```

---

## 6. Usage

### Ingest job descriptions

```bash
python cli.py ingest
```

Creates the Chroma collection and inserts all job records. Prints a summary with the document count.

### Search

```bash
python cli.py search "Python backend engineer with FastAPI and PostgreSQL"
```

Returns the top 5 matching jobs with titles, companies, locations, categories, and cosine distances.

### Search with metadata filters

```bash
python cli.py search "engineer" --category Backend
python cli.py search "engineer" --location Cairo
python cli.py search "engineer" --category Backend --location Cairo
```

Combines semantic similarity with structured metadata filtering.

### Multiple queries

```bash
python cli.py search "Python backend engineer" "Kubernetes DevOps engineer" "AI engineer with RAG experience"
```

Each query independently returns its top matches, grouped by query in the output.

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
3. **Expect distance 0–1** — lower is better, but the exact meaning depends on the model. `all-MiniLM-L6-v2` is a general-purpose model.
4. **Different models behave differently** — try `all-MiniLM-L12-v2` or `MPNet` for comparison.
5. **Metadata filtering + semantic search** = most powerful combination — "Find AI jobs in Cairo" works best with both.

---

## 10. Evaluation metrics reference

| Metric | Definition | Interpretation |
|---|---|---|
| **Hit@K** | Expected job in top K results | Percentage of queries where at least one expected job appears |
| **Precision@K** | (Relevant in top K) / K | Of top K, what fraction are relevant |
| **Recall@K** | (Relevant in top K) / (Total relevant) | Of all relevant, what fraction appear in top K |
