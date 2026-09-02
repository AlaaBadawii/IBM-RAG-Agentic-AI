# Similarity Search on Employee Records

A ChromaDB-based demonstration of semantic similarity search and metadata filtering on employee records. Uses **SentenceTransformers** (`all-MiniLM-L6-v2`) to embed employee data and perform advanced search operations including similarity search, metadata filtering, and combined semantic + metadata queries.

This project is part of **Course 3 — Vector Databases for RAG: An Introduction** (IBM RAG and Agentic AI Professional Certificate), providing hands-on experience with ChromaDB collections, embeddings, and retrieval.

---

## 1. What this project does

The application demonstrates core vector database concepts:

1. **Creates** a ChromaDB collection (`employee_collection`) with cosine distance and a SentenceTransformer embedding function
2. **Ingests** employee records — each employee's role, experience, department, skills, location, and employment type are embedded into a searchable vector
3. **Performs similarity search** — find employees similar to a natural-language query (e.g., "Python developer with web development experience")
4. **Filters by metadata** — retrieve all employees by department, experience level, or location using `collection.get(where=...)`
5. **Combines semantic search + metadata filtering** — find senior Python developers in major tech cities using `collection.query()` with `where` filters

---

## 2. Dataset

Employee records are defined in `data/employee.py` (`EMPLOYEES_DATA`). Each record contains:

| Field | Description |
|---|---|
| `id` | Unique identifier |
| `name` | Employee name |
| `role` | Job role (e.g., "Senior Python Developer", "Data Scientist") |
| `department` | Department (e.g., "Engineering", "Product") |
| `experience` | Years of experience |
| `skills` | Comma-separated list of skills |
| `location` | City (e.g., "San Francisco", "New York") |
| `employment_type` | Full-time, Part-time, Contract, etc. |

The searchable document for each employee combines role, experience, department, skills, location, and employment type into a single text string.

---

## 3. Search capabilities demonstrated

### Pure similarity search

```python
collection.query(query_texts=["Python developer with web development experience"], n_results=3)
```

Finds the 3 most similar employees based on semantic embedding of the query.

### Metadata filtering

```python
# All Engineering employees
collection.get(where={"department": "Engineering"})

# Employees with 10+ years experience
collection.get(where={"experience": {"$gte": 10}})

# Employees in specific locations
collection.get(where={"location": {"$in": ["San Francisco", "Los Angeles"]}})
```

### Combined search: similarity + metadata filtering

```python
collection.query(
    query_texts=["Senior Python developer full stack"],
    n_results=5,
    where={"$and": [{"experience": {"$gte": 8}}, {"location": {"$in": ["San Francisco", "New York", "Seattle"]}}]}
)
```

Finds the most similar senior Python developers with 8+ years of experience in major tech cities.

---

## 4. Project structure

```
Similarity_Search_on_Employee_Records/
├── similarity_employeedata.py   # Main script: create collection, ingest, search
├── data/
│   └── employee.py            # EMPLOYEES_DATA — the employee records
└── README.md                  # This file
```

---

## 5. How it works

1. **Embedding function** — `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` converts text into 384-dimensional vectors.
2. **Collection creation** — `client.create_collection()` creates the `employee_collection` with cosine distance and the embedding function.
3. **Ingestion** — Each employee record is converted into a document string and associated metadata, then added via `collection.add()`.
4. **Search** — `collection.query()` accepts `query_texts`, `n_results`, and optional `where` filters, returning IDs, documents, metadatas, and distances.
5. **Filtering** — `collection.get()` with a `where` parameter retrieves documents matching metadata criteria (exact match, `$gte`, `$lte`, `$in`, `$and`, etc.).

---

## 6. Setup

**Requirements:** Python 3.10+, internet access for downloading the embedding model on first run.

```bash
cd Similarity_Search_on_Employee_Records
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install chromadb sentence-transformers torch
```

---

## 7. Run

```bash
python similarity_employeedata.py
```

The script will:

1. Create the `employee_collection` in ChromaDB
2. Embed and ingest all employee records
3. Run 6 demonstration searches, printing results to the console:

| # | Search type | Query |
|---|---|---|
| 1 | Similarity | "Python developer with web development experience" |
| 2 | Similarity | "team leader manager with experience" |
| 3 | Metadata filter | All Engineering employees |
| 4 | Metadata filter | Employees with 10+ years experience |
| 5 | Metadata filter | Employees in California |
| 6 | Combined | Senior Python developers in major tech cities (8+ years) |

---

## 8. Key concepts practiced

- **ChromaDB collections** — creating, ingesting, and querying a persistent vector store
- **SentenceTransformer embeddings** — converting text to vectors with `SentenceTransformerEmbeddingFunction`
- **Cosine distance** — the distance metric used; 0 = identical, 1 = opposite
- **Metadata filtering** — using `where` clauses in `collection.get()` for structured filtering
- **Combined search** — using `where` in `collection.query()` to filter semantic results
- **Document construction** — combining multiple fields into an effective searchable text string

---

## 9. ChromaDB where filter operators

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"department": "Engineering"}` | Equal to value |
| Greater than | `{"experience": {"$gte": 10}}` | Greater than or equal |
| In list | `{"location": {"$in": ["SF", "NYC"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |
| Or | `{"$or": [cond1, cond2]}` | At least one condition matches |

---

## 10. Ideas to extend

- Add more employees and test retrieval quality across a larger dataset
- Experiment with different embedding models and compare results
- Build a Gradio or Streamlit UI for interactive search
- Add persistence by using `chromadb.PersistentClient` instead of `chromadb.Client()`
- Implement update and delete operations on the collection
- Add evaluation with test queries and relevance judgments
