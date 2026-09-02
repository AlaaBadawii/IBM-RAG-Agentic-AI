# Job Description Matcher - Project Plan

A comprehensive Python application that stores job descriptions in Chroma DB, generates embeddings using SentenceTransformers, and enables natural-language semantic search. This project follows the IBM lab progression from document storage to similarity search with metadata filtering and evaluation.

---

## Project Overview

The Job Description Matcher bridges the gap between learned retrieval concepts and practical implementation. The application:

- **Stores** ~30 job descriptions in Chroma DB with rich metadata
- **Generates** embeddings using `all-MiniLM-L6-v2` (SentenceTransformers)
- **Enables** natural-language semantic search with similarity scoring
- **Provides** metadata filtering (category, location)
- **Supports** experimentation and evaluation metrics

### Core Philosophy

> "You're not just learning: 'Chroma returns similar documents.'
> You're learning: 'What does my embedding model consider semantically similar?'"

The project progresses from basic vector storage through metadata filtering to experimentation and evaluation—mirroring the transition from IBM lab exercises to independent retrieval system design.

---

## Sub-Task 1 — Project Scaffold & Configuration

### Status: [pending]

### Intent

Establish the foundation for the application. This task focuses on project structure, dependency management, and configuring the two core technologies: Chroma DB and SentenceTransformers.

### Expected Outcomes

#### Project Directory Structure

```
job_description_matcher/
├── config.py          # Configuration constants
├── data.py            # Job dataset
├── vector_store.py    # Chroma DB operations
├── search.py          # Semantic search logic
├── cli.py             # Command-line interface
├── requirements.txt   # Python dependencies
├── .gitignore         # Excludes Chroma data directory
├── .env.example       # Example environment variables (if needed)
└── plan.md            # This project plan
```

#### requirements.txt

```
chromadb
sentence-transformers
torch
```

**Rationale**: `chromadb` for vector storage, `sentence-transformers` for embeddings, `torch` as the underlying framework for the SentenceTransformer model.

#### config.py

Defines all configurable parameters in a single location:

```python
# config.py

# Embedding model configuration
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Chroma collection configuration
COLLECTION_NAME = "jobs"
PERSISTENCE_DIRECTORY = "./data/chroma"
DEFAULT_NUM_RESULTS = 5

# Distance metric
DISTANCE_METRIC = "cosine"
```

**Key Decisions**:
- `all-MiniLM-L6-v2`: The IBM lab's specified model—small, fast, and effective for general semantic similarity
- Persistence directory: `./data/chroma`—data survives between runs
- Default results: 5—balance between comprehensiveness and noise

#### .gitignore

```
# Chroma DB persistence data
data/chroma/

# Python bytecode cache
__pycache__/
*.pyc
*.pyo

# Environment variables
.env
```

**Critical**: The `data/chroma/` directory must never be committed, as it contains persistent database files that change with every run.

### Learning Outcomes

- Understand dependency management for Chroma + SentenceTransformers
- Configure embedding model selection (critical for search behavior)
- Set up persistent storage that survives application restarts
- Structure configuration for easy modification later

---

## Sub-Task 2 — Create the Job Dataset

### Status: [pending]

### Intent

Replace synthetic datasets (like IBM's grocery dataset) with realistic job descriptions. This task teaches exactly what gets stored in a vector database: the searchable text, metadata, and unique identifiers.

### Expected Outcomes

#### Job Record Structure

Each job is a dictionary with these fields:

| Field        | Purpose                              |
|--------------|--------------------------------------|
| `id`         | Unique identifier (e.g., "job_001")  |
| `title`      | Job title (e.g., "Backend Software Engineer") |
| `company`    | Company name                         |
| `location`   | Job location (city or "Remote")      |
| `category`   | Broad technical category             |
| `description`| Full job description text            |

**Example**:

```python
{
    "id": "job_001",
    "title": "Backend Software Engineer",
    "company": "TechCorp",
    "location": "Cairo",
    "category": "Backend",
    "description": "Build REST APIs using Python, FastAPI and PostgreSQL..."
}
```

#### Searchable Text vs. Metadata Separation

This is a **critical concept**:

- **Searchable text** (`documents` in Chroma): The free-text description that gets embedded. Typically combines title + description for optimal semantic matching.
- **Metadata** (`metadatas` in Chroma): Structured fields used for filtering. Includes category, location, company—fields you want to filter on without semantic search.

```python
# What gets embedded (searchable text):
"Build REST APIs using Python, FastAPI and PostgreSQL. Work on high-traffic services..."

# What gets stored as metadata (for filtering):
{"title": "Backend Software Engineer", "company": "TechCorp", "location": "Cairo", "category": "Backend"}
```

#### Dataset Requirements

- **20-30 job records** with genuinely different technical profiles
- Coverage across these domains:
  - Backend
  - AI/ML
  - DevOps
  - Cloud
  - Data Engineering
  - QA
  - Mobile
  - Frontend
  - Full Stack

**Design Principle**: No two jobs should have identical technical profiles. A "Backend Engineer" and a "DevOps Engineer" should have distinct descriptions emphasizing different skills, even if they both involve servers.

#### Searchable Text Construction

Recommendation: Combine title and description for embedding:

```python
searchable_text = f"{job['title']}: {job['description']}"
```

This ensures the job title influences semantic similarity while the description provides detail.

### Learning Outcomes

- Understand the anatomy of a vector database record
- Distinguish between embedded text (semantic) and metadata (filtering)
- Design diverse technical profiles that yield meaningful search results
- Learn why separating searchable text from metadata matters for filtering later

---

## Sub-Task 3 — Chroma Collection & Document Ingestion

### Status: [pending]

### Intent

Build the component that creates the Chroma collection and inserts all job records. This is the "pipeline" task—transforming static data into searchable vectors.

### Expected Outcomes

#### Running `python cli.py ingest`

Should produce output like:

```
Creating collection...
Embedding jobs...
Inserted 25 jobs.
Collection ready.
```

#### vector_store.py Implementation

Key responsibilities:

1. **Initialize Chroma client** with persistence settings
2. **Configure SentenceTransformer embedding function** using `all-MiniLM-L6-v2`
3. **Create/get collection** with cosine distance metric
4. **Convert job records** into Chroma-compatible formats
5. **Add to Chroma** using `collection.add()`
6. **Verify** the collection contains the expected number of documents

#### Code Flow

```python
# vector_store.py (simplified)

vector_store = ChromaClient(persist_directory="./data/chroma")
embedding_fn = SentenceTransformer("all-MiniLM-L6-v2")

collection = vector_store.get_or_create_collection(
    name="jobs",
    metadata={"distance_metric": "cosine"}
)

# Prepare data
ids = [job["id"] for job in jobs]
documents = [job["searchable_text"] for job in jobs]
metadatas = [
    {
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "category": job["category"],
    }
    for job in jobs
]

# Add to collection
collection.add(ids=ids, documents=documents, metadatas=metadatas)

# Verify
count = collection.count()
print(f"Inserted {count} jobs.")
```

#### Verification

After ingestion, confirm:

- Collection contains exactly the expected number of documents (20-30)
- IDs match the original dataset exactly
- Documents and metadatas are correctly associated with IDs
- A small sample display shows correct data

### Learning Outcomes

- Chroma DB client initialization and persistence
- SentenceTransformer integration for custom embedding functions
- The `collection.add()` API: IDs, documents, and metadata
- Cosine distance configuration and why it matters
- Verification that data round-trips correctly

---

## Sub-Task 4 — Inspect the Vector Database

### Status: [pending]

### Intent

Before implementing search, understand exactly what's stored. This inspection task is essential—it confirms data integrity and builds intuition for how Chroma organizes information.

### Expected Outcomes

#### Inspection Function

Create a function that displays:

```
Collection: jobs
Documents: 25

job_001
Backend Software Engineer
Backend
Cairo

job_002
DevOps Engineer
DevOps
Giza
```

#### Using `collection.get()`

The IBM lab pattern:

```python
# Retrieve all stored data
stored = collection.get(include=["documents", "metadatas"])

print(f"Collection: {collection.name}")
print(f"Documents: {len(stored['ids'])}")

for i in range(len(stored['ids'])):
    print(f"\n{stored['ids'][i]}")
    print(f"{stored['documents'][i][:80]}...")  # Truncate for display
    print(f"Category: {stored['metadatas'][i]['category']}")
    print(f"Location: {stored['metadatas'][i]['location']}")
```

#### Confirmation Checklist

- [ ] Number of stored jobs matches the original dataset
- [ ] IDs match exactly (job_001, job_002, ..., job_030)
- [ ] Metadata fields are accessible (title, company, location, category)
- [ ] Documents are the searchable text strings
- [ ] Sample records display correctly

### Learning Outcomes

- `collection.get()` retrieves stored data for inspection
- Understanding the relationship between IDs, documents, and metadata
- Building intuition for what Chroma stores internally
- Debugging data ingestion issues

---

## Sub-Task 5 — Basic Semantic Search

### Status: [pending]

### Intent

Implement the core functionality: natural-language query → semantically similar jobs. This is the heart of the application.

### Expected Outcomes

#### search_jobs() Function

```python
def search_jobs(vector_store, query, n_results=5):
    """
    Search for jobs semantically similar to the query.
    
    Args:
        vector_store: Initialized VectorStore instance
        query: Natural language job search query
        n_results: Number of top results to return
    
    Returns:
        list of dicts with formatted job results
    """
```

#### Query Execution

Use Chroma's `collection.query()`:

```python
results = collection.query(
    query_texts=[query],
    n_results=n_results,
    include=["documents", "metadatas", "distances"]
)
```

#### Result Extraction

Extract and format:

- **IDs**: `results["ids"][0]` - list of job IDs
- **Documents**: `results["documents"][0]` - searchable text strings
- **Metadata**: `results["metadatas"][0]` - structured fields
- **Distances**: `results["distances"][0]` - cosine similarity distances

#### Clean Python Structure

Return results as a list of dicts:

```python
[
    {
        "id": "job_003",
        "title": "AI/ML Engineer",
        "company": "InnovateAI",
        "location": "Remote",
        "category": "AI",
        "description": "Develop machine learning models for NLP...",
        "distance": 0.18,
    },
    ...
]
```

#### Query Examples

1. `"Python backend engineer with FastAPI and PostgreSQL"` → Should return Backend/Software Engineer jobs near the top
2. `"I want to work with Kubernetes, Docker and cloud infrastructure"` → Should return DevOps/Cloud jobs

### Learning Outcomes

- Chroma's `collection.query()` API for similarity search
- Distance scores (cosine distance: 0 = identical, 1 = opposite)
- Extracting and formatting returned data
- Expected behavior for technical queries

---

## Sub-Task 6 — Build the CLI Search Experience

### Status: [pending]

### Intent

Transform the underlying search function into a usable command-line interface. This task focuses on UX, error handling, and making the application actually runnable.

### Expected Outcomes

#### Running `python cli.py search`

Should produce interactive output:

```
Job Description Matcher
Enter your job requirements:
> Python backend engineer with FastAPI and Docker

Top 5 matches:

1. Backend Software Engineer
   Company: TechCorp
   Location: Cairo
   Category: Backend
   Distance: 0.18

2. Python API Engineer
   Company: Interface Inc.
   Location: Remote
   Category: Backend
   Distance: 0.21
```

#### CLI Features

1. **Ingest command**: `python cli.py ingest`
   - Adds all jobs to the Chroma collection
   - Prints summary (count, ready message)

2. **Search command**: `python cli.py search`
   - Prompts: "Enter your job requirements: > "
   - Calls `search_jobs()`
   - Formats and displays top 5 results

3. **Error handling** (three scenarios):
   - **Empty query**: "Query cannot be empty. Please try again."
   - **Empty collection**: "No jobs in the collection. Run 'ingest' first."
   - **Chroma errors**: Graceful handling of database issues

#### Command-Line Mode

Also support direct queries:

```
python cli.py search "Python backend engineer"
```

#### Code Structure

```
cli.py responsibilities:
- Show application banner
- Handle command-line arguments
- Route to ingest or search subroutines
- Handle interactive input/output
- Graceful error messages
```

### Learning Outcomes

- CLI design patterns (argument parsing, interactive input)
- User feedback and result formatting
- Error handling for common user mistakes
- Both interactive and programmatic usage modes

---

## Sub-Task 7 — Multiple Queries

### Status: [pending]

### Intent

Practice the multiple-query functionality from the IBM lab, extending beyond a single search query.

### Expected Outcomes

#### Supporting Multiple Queries

```bash
python cli.py search \
  "Python backend engineer" \
  "Kubernetes DevOps engineer" \
  "AI engineer with RAG experience"
```

Each query independently returns its top matches.

#### Implementation Approach

Two patterns to understand:

1. **One Chroma query call per query**: Loop through queries, call `collection.query()` for each
2. **Batch query**: Pass multiple query texts to Chroma at once (newer Chroma versions)

```python
# Pattern: One query per loop iteration
for query in queries:
    results = collection.query(
        query_texts=[query],
        n_results=5,
        include=["documents", "metadatas", "distances"]
    )
    # Process results for this query
```

#### Output Grouping

Print results grouped by query:

```
Query 1: "Python backend engineer"
------------------------------
1. Backend Software Engineer - Distance: 0.18
2. Python API Engineer - Distance: 0.21

Query 2: "Kubernetes DevOps engineer"
--------------------------------------
1. DevOps Engineer - Distance: 0.12
2. Container Specialist - Distance: 0.15

Query 3: "AI engineer with RAG experience"
------------------------------------------
1. AI/ML Engineer - Distance: 0.10
```

#### Verification

- Each query produces independent results
- Result arrays are correctly handled (no cross-contamination)
- Output clearly associates results with their query

### Learning Outcomes

- Processing multiple queries in one session
- Correctly associating result sets with their originating queries
- Output formatting for comparative display
- The IBM lab's explicit pattern change from one query to multiple

---

## Sub-Task 8 — Metadata Filtering

### Status: [pending]

### Intent

Combine semantic search with metadata filtering. This is where the project becomes genuinely useful—finding jobs that match both content AND structured criteria.

### Expected Outcomes

#### Filter Scenarios to Support

1. **Semantic search without filters**: Baseline behavior
   ```bash
   python cli.py search "Python backend engineer"
   ```

2. **Semantic search with category filter**:
   ```bash
   python cli.py search "engineer" --category Backend
   # Or: find backend jobs regardless of keywords
   ```

3. **Semantic search with location filter**:
   ```bash
   python cli.py search "engineer" --location Cairo
   # Or: find Cairo jobs regardless of keywords
   ```

4. **Semantic search with both filters**:
   ```bash
   python cli.py search "engineer" --category Backend --location Cairo
   ```

#### Implementation Pattern

Chroma supports where-filters in the query:

```python
results = collection.query(
    query_texts=[query],
    n_results=5,
    where={"category": "Backend", "location": "Cairo"},
    include=["documents", "metadatas", "distances"]
)
```

#### Expected Behavior

- Filters narrow the search space while semantic search ranks by similarity
- Results should satisfy both the query semantics AND the metadata filters
- Compare results across the four scenarios above

#### Example Interactions

```
$ python cli.py search "backend" --category Backend
Collection: 30 jobs
Searching for: "backend" with category=Backend

Top 5 matches:
1. Backend Software Engineer - Distance: 0.15 (Category: Backend, Location: Cairo)
2. Backend Engineer - Distance: 0.18 (Category: Backend, Location: Giza)
```

### Learning Outcomes

- Chroma's `where` filter parameter
- Combining semantic similarity with structured filtering
- How filters affect search space and result quality
- Practical use cases: "Find AI jobs in Cairo" or "Remote DevOps roles"

---

## Sub-Task 9 — Search Experimentation

### Status: [pending]

### Intent

Investigate how semantic search actually behaves. This is the "exploration" task—moving from making it work to understanding what your embedding model considers similar.

### Expected Outcomes

#### 10 Queries to Run

| Query                                | Expected Theme          |
|--------------------------------------|-------------------------|
| "Python API development"             | Backend/FastAPI         |
| "backend web services"               | Backend/General         |
| "container orchestration"            | DevOps/Kubernetes       |
| "artificial intelligence retrieval systems" | AI/Retrieval         |
| "database engineering"               | Data Engineering        |
| "cloud infrastructure"               | Cloud                   |
| "mobile application development"     | Mobile                  |
| "full stack web developer"           | Full Stack              |
| "data science and machine learning"  | AI/ML                   |
| "DevOps and CI/CD pipeline"          | DevOps                  |

#### For Each Query, Record

- Top 5 job IDs and titles
- Distance scores (0-1 range)
- Whether results "make sense" semantically

#### Analysis Categories

**Surprising matches**: Jobs appear that you wouldn't expect based on keywords

**Bad matches**: Jobs appear that clearly shouldn't—examine why

**Keyword vs. semantic similarity**: Does the model understand context, or just keywords?

#### Write-Up: "What I Learned About Embeddings"

Document insights such as:

- "The model conflates 'Docker' with 'container orchestration' even when separated"
- "Backend queries sometimes return Mobile jobs due to 'app' keyword overlap"
- "Remote vs. on-site distinctions are not well-captured by this model"
- "Category metadata provides more reliable filtering than semantic similarity alone"

### Learning Outcomes

- Empirical understanding of embedding model behavior
- Critical analysis of search quality
- Distinguishing between keyword matching and true semantic similarity
- Writing about technical observations

---

## Sub-Task 10 — Evaluation Dataset

### Status: [pending]

### Intent

Introduce formal evaluation discipline. Instead of just "it seems to work," measure hit rate metrics.

### Expected Outcomes

#### Create ~10 Test Queries

Define manually which jobs should be relevant:

```
Query: "Python FastAPI backend developer"
Expected relevant: job_001, job_011, job_015
```

#### Calculate Metrics

For each query, check if expected jobs appear in top K:

| Metric | Definition |
|--------|------------|
| **Hit@3** | Expected job is in top 3 results |
| **Hit@5** | Expected job is in top 5 results |
| **Precision@3** | Fraction of top 3 that are expected relevant |

#### Example Calculation

```
Query: "Python FastAPI backend developer"
Top 5 results: [job_001, job_005, job_011, job_003, job_015]
Expected:      [job_001, job_011, job_015]

Hit@3: job_001 is in top 3 → TRUE → Hit@3 = 1
Hit@5: 3 of 5 expected are in top 5 → Precision@5 = 3/5 = 0.6
Precision@3: 2 of top 3 are expected → Precision@3 = 2/3 = 0.67
```

#### Summary Statistics

 Across all 10 queries:

```
Hit@3 rate: 7/10 = 70%
Hit@5 rate: 25/50 = 50%
Precision@3 average: 0.58
```

### Learning Outcomes

- Formal evaluation of retrieval system quality
- Hit@k and Precision@k metrics (from RAG work)
- Comparing expected vs. actual performance
- Using evaluation to identify model limitations

---

## Sub-Task 11 — Refactor the Architecture

### Status: [pending]

### Intent

Clean up the codebase once everything works. A proper architecture separates concerns and makes the system maintainable.

### Expected Outcomes

#### Final Architecture

```
                 ┌──────────────┐
                 │    cli.py    │
                 └──────┬───────┘
                        │
             ┌──────────▼──────────┐
             │      search.py      │
             └──────────┬──────────┘
                        │
             ┌──────────▼──────────┐
             │   vector_store.py   │
             └──────────┬──────────┘
                        │
                  ┌─────▼─────┐
                  │  Chroma   │
                  └───────────┘
```

#### Refactoring Checklist

1. **Remove duplicated code** - Search logic in one place only
2. **Separate configuration from logic** - config.py drives behavior
3. **Separate data from database logic** - data.py has jobs, vector_store.py has Chroma ops
4. **Separate database logic from search logic** - search.py uses vector_store, not direct Chroma calls
5. **Add type hints** - Function signatures with types
6. **Add docstrings** - All public functions documented
7. **Add basic exception handling** - Try/except for Chroma errors
8. **Update README** - Document usage, installation, and known issues

#### Type Hints Example

```python
# search.py
from typing import List, Dict, Any
from vector_store import VectorStore

def search_jobs(vector_store: VectorStore, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Search for jobs semantically similar to query."""
    ...
```

#### Exception Handling Example

```python
try:
    results = vector_store.query(query, n_results=n_results)
except chromadb.errors.ChromaError as e:
    print(f"Search error: {e}")
    return []
```

### Learning Outcomes

- Clean architecture principles (separation of concerns)
- Type hints for code maintainability
- Docstrings for API documentation
- Exception handling for robustness

---

## Sub-Task 12 — Optional Phase: Add an LLM

### Status: [pending]

### Intent (Do only after vector-search works properly)

Transform the output from "here are similar jobs" to "here is an analysis of the best jobs for you."

### Transformation

```
Before:
User query → Chroma → Top 5 jobs → Display in CLI

After:
User query → Chroma similarity search → Top 5 jobs → LLM → "Here are the jobs that best match you..."
```

### LangChain LCEL Pattern

```
Prompt → LLM → Structured Output
```

Connects this exercise with the Book_Movie_Advisor project's techniques.

### Example Flow

```
1. User: "Python backend engineer with FastAPI"
2. Chroma returns top 5 jobs with distances
3. LLM receives: "Here are 5 jobs matching your query..."
4. LLM outputs structured analysis:
   "Based on your query, the best matches are:
   1. Backend Software Engineer at TechCorp (Cairo) - Very strong match on Python/FastAPI
   2. Python API Engineer at Interface Inc. (Remote) - Strong match on FastAPI experience
   3. ..."
```

### Why This Matters

- Bridges vector search with LLM capabilities you've already learned
- Provides natural language summaries instead of raw results
- Demonstrates the retrieval → generation pattern (RAG-lite)
- Prepares for future Full-Stack AI application development

### Learning Outcomes

- LangChain LCEL for structured pipeline building
- LLM prompt engineering for job analysis
- Combining retrieval with generation
- Connection to prior project knowledge

---

## Additional Resources

### Embedding Model Reference

- `all-MiniLM-L6-v2`: 384-dimensional embeddings, trained on 1 billion sentence pairs
- Cosine distance range: 0 (identical) to 1 (opposite)
- Smaller distances = more semantically similar

### Chroma DB Key Concepts

| Concept | Description |
|---------|-------------|
| Collection | Logical grouping of documents (like a table) |
| Document | A piece of text + metadata (what gets embedded) |
| ID | Unique identifier for each document |
| Metadata | Structured key-value pairs for filtering |
| Distance metric | How similarity is measured (cosine, euclidean, dot) |

### Semantic Search Best Practices

1. **Combine title + description** for searchable text
2. **Use metadata for filtering**, not semantic similarity
3. **Expect distance 0-1**: Lower is better, but exact meaning depends on model
4. **Different models behave differently**: all-MiniLM-L6-v2 is general-purpose
5. **Metadata filtering + semantic search** = most powerful combination

### Evaluation Metrics Quick Reference

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Hit@K** | Expected job in top K results | Percentage of queries where at least one expected job appears |
| **Precision@K** | (Relevant in top K) / K | Of top K, what fraction are relevant |
| **Recall@K** | (Relevant in top K) / (Total relevant) | Of all relevant, what fraction appear in top K |

---

## Project Success Criteria

The project is complete when:

- [ ] `python cli.py ingest` successfully stores all jobs
- [ ] `python cli.py search "query"` returns top 5 results with distances
- [ ] `python cli.py search "query" --category Backend` filters by category
- [ ] `python cli.py search "query" --location Cairo` filters by location
- [ ] Multiple queries work: `python cli.py search "q1" "q2" "q3"`
- [ ] Evaluation metrics (Hit@3, Hit@5, Precision@3) are calculated
- [ ] Code is refactored with type hints and docstrings
- [ ] Plan.md is updated through Sub-Task 11

---

## Next Steps After Completion

1. **Experiment with different embedding models** (all-MiniLM-L12-v2, MPNet, etc.)
2. **Add more job categories** or expand the dataset
3. **Try the optional LLM phase** with LangChain
4. **Experiment with hybrid search** (keyword + semantic)
5. **Convert to FastAPI** for a web interface
6. **Evaluate with test sets** from real job posting data

---