# Food Recommendation System — Learning Lab

Welcome! In this lab, you will build a food recommendation system using **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`) for semantic search. By the end, you will understand how computers can recommend food by *meaning*, not just by exact keywords.

The project progresses through three systems of increasing sophistication:

```text
Interactive Similarity Search
        ↓
Advanced Search with Metadata Filtering
        ↓
RAG Chatbot with LLM Integration
```

---

## 1. What You'll Build

You will build a Python application that:

- Stores food records in a **vector database** (ChromaDB)
- Converts food descriptions into numerical representations called **embeddings**
- Searches for food by *concept* (e.g., "chocolate dessert") instead of exact keywords
- Filters food by structured fields like cuisine type and calories
- Generates conversational recommendations using a **Retrieval-Augmented Generation (RAG)** pipeline

The final project contains three search systems:

```text
                         Food Dataset
                              │
                              ↓
                       Data Preparation
                              │
                              ↓
                         Embeddings
                              │
                              ↓
                           ChromaDB
                              │
              ┌───────────────┼────────────────┐
              ↓               ↓                ↓
       Interactive       Advanced Search    RAG Chatbot
          Search          + Filtering           │
              │               │                ↓
              │               │              LLM
              │               │                │
              └───────────────┴────────────────┘
                              ↓
                     Food Recommendations
```

---

## 2. What You'll Learn

By following this lab, you will understand:

- What **embeddings** are and why they matter
- How a **vector database** differs from a traditional database
- How to use **ChromaDB** to store and search vectors
- The difference between **documents** (text for similarity) and **metadata** (structured fields for filtering)
- How **semantic similarity search** works
- How to filter results using ChromaDB's `where` expressions
- How to combine semantic search with metadata filters
- How **RAG** works — retrieving relevant data and sending it to an LLM
- Why conversational agents benefit from retrieval rather than relying on LLM knowledge alone

---

## 3. Prerequisites

- **Python 3.10+**
- Basic familiarity with **Python functions, classes, and modules**
- Basic understanding of what a **database** is
- No prior knowledge of vector databases or RAG required

### Setup

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install chromadb sentence-transformers torch
```

> **Note:** The `ibm_watsonx_ai` package is used by the RAG chatbot. Install it with `pip install ibm-watsonx` if you want to run the full RAG system. Alternatively, the `system_comparison.py` script runs the first two systems without requiring any LLM.

---

## 4. Project Overview

### The Dataset

The project uses `data/FoodDataSet.json`, a JSON array containing food records. Each record has:

| Field | Example | Type |
|---|---|---|
| `food_id` | `1` | integer |
| `food_name` | `"Chocolate Cake"` | string |
| `food_description` | `"A rich, moist cake made with..."` | string |
| `food_calories_per_serving` | `450` | integer |
| `food_nutritional_factors` | `{"carbohydrates": "58g", ...}` | dict |
| `food_ingredients` | `["Flour", "Sugar", ...]` | list |
| `food_health_benefits` | `"Contains antioxidants from cocoa"` | string |
| `cooking_method` | `"Baking"` | string |
| `cuisine_type` | `"American"` | string |
| `food_features` | `{"taste": "sweet", ...}` | dict |

### Key Files

| File | Purpose |
|---|---|
| `data/FoodDataSet.json` | The food dataset |
| `app/shared_functions.py` | Core functions: data loading, collection creation, population, search |
| `app/interactive_search.py` | Interactive CLI food search chatbot |
| `app/advanced_search.py` | Advanced search with filtering and interactive menus |
| `app/enhanced_rag_chatbot.py` | RAG chatbot with LLM integration |
| `app/system_comparison.py` | Side-by-side comparison of all three systems |

---

## 5. Phase 1 — Prepare the Dataset

### 1. What are we learning?

**Data preparation** — understanding the raw data before using it. The food dataset is stored in JSON format, which is a common format for data exchange.

### 2. What are we building?

The `load_food_data()` function reads the JSON file and normalizes the data:

```python
def load_food_data(file_path: str) -> list[dict]:
    """Load food data from JSON file"""
    with open(file_path, "r", encoding="utf-8") as file:
        food_data = json.load(file)
    # Normalize each item's fields
    for i, item in enumerate(food_data):
        if "food_id" not in item:
            item["food_id"] = str(i + 1)
        # Ensure required fields exist...
    return food_data
```

### 3. What should you implement?

The `load_food_data()` function already exists in `shared_functions.py`. It:
1. Reads the JSON file
2. Normalizes food IDs to strings
3. Ensures required fields exist (ingredients, description, cuisine type, calories)
4. Extracts taste profiles from nested `food_features`

### 4. How do you verify it?

```bash
python -c "from shared_functions import load_food_data; data = load_food_data('data/FoodDataSet.json'); print(f'{len(data)} food items loaded')"
```

You should see the total number of food items in the dataset.

---

## 6. Phase 2 — Understand Embeddings

### 1. What are we learning?

**Embeddings** are numerical representations of text. The model `all-MiniLM-L6-v2` converts text into **384-dimensional vectors** — lists of 384 floating-point numbers.

Here is the intuition:

- Similar texts produce vectors that are **close together** in this 384-dimensional space.
- Dissimilar texts produce vectors that are **far apart**.
- The distance between vectors measures semantic similarity.

### 2. Why do food descriptions need embeddings?

When you search for "chocolate dessert", you are not looking for items that literally contain the word "chocolate" and "dessert". You want items that *mean* chocolate dessert — perhaps "Chocolate Lava Cake" or "Molten Chocolate Cake". Embeddings capture this semantic meaning.

### 3. What are we building?

The embedding function is configured in `shared_functions.py`:

```python
from chromadb.utils import embedding_functions

sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
```

The model used is `all-MiniLM-L6-v2`, which produces **384-dimensional vectors** using cosine distance.

### 4. How do you verify it?

```bash
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
v = model.encode(['hello world'])
print(f'Vector dimension: {v.shape[1]}')
print(f'First 5 values: {v[0][:5]}')
"
```

You should see `Vector dimension: 384`.

---

## 7. Phase 3 — Set Up ChromaDB

### 1. What are we learning?

**ChromaDB** is a vector database. A vector database stores vectors (lists of numbers) and can find the most similar vectors quickly.

Key ChromaDB concepts:

- **Client** — the connection to the database. `chromadb.Client()` creates an in-memory client.
- **Collection** — a named container for vectors, similar to a table in a relational database.
- **ID** — a unique string identifier for each stored item.
- **Embedding Function** — automatically converts text to vectors when documents are added or queried.

### 2. What are we building?

The `create_similarity_search_collection()` function creates a ChromaDB collection:

```python
def create_similarity_search_collection(
    collection_name: str, collection_metadata: dict | None = None
):
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.create_collection(
        name=collection_name,
        metadata=collection_metadata,
        embedding_function=sentence_transformer_ef,
    )
```

### 3. What should you implement?

The collection creation handles:
1. Deleting any existing collection with the same name
2. Creating a new collection with the embedding function
3. Returning the collection object

### 4. How do you verify it?

```bash
python -c "
from shared_functions import create_similarity_search_collection
collection = create_similarity_search_collection('test_collection')
print('Collection name:', collection.name)
"
```

You should see the collection name printed without errors.

---

## 8. Phase 4 — Generate Embeddings

### 1. What are we learning?

**Embedding generation** — when you add a document to a ChromaDB collection, the embedding function automatically converts the text into a vector. When you query the collection, the query text is also converted to a vector, and ChromaDB finds the closest stored vectors.

### 2. What are we building?

The `populate_similarty_collection()` function builds documents and metadata for each food item:

```python
def populate_similarty_collection(collection, food_items):
    documents = []
    metadatas = []
    ids = []

    for food in food_items:
        # Build searchable text from multiple fields
        text = f"Name: {food['food_name']}."
        text += f" Description: {food.get('food_description', '')}."
        text += f" Ingredients: {', '.join(food.get('food_ingredients', []))}."
        text += f" Cuisine: {food.get('cuisine_type', 'Unknown')}."
        # ... more fields

        documents.append(text)
        metadatas.append({
            "name": food["food_name"],
            "description": food["food_description"],
            "cuisine_type": food["cuisine_type"],
            "calories": food["food_calories_per_serving"],
            # ... more metadata
        })
        ids.append(str(food["food_id"]))

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
```

### 3. Key distinction: Documents vs. Metadata

This is one of the most important concepts in vector databases:

- **Documents** (searchable text): the free-text string that gets embedded. Combines name, description, ingredients, cuisine, taste profile, nutritional information, and health benefits. This is what gets semantically searched.
- **Metadata** (structured fields): key-value information used for filtering. Includes name, description, cuisine_type, calories, cooking_method, taste_profile, health_benefits. These are what get filtered.

**They serve different purposes:**
- **Documents** answer: *"What is conceptually similar?"*
- **Metadata** answers: *"What satisfies this structured constraint?"*

### 4. Why is metadata cleaning important?

ChromaDB metadata can only contain simple types (str, int, float, bool, list). Nested dictionaries like `food_nutritional_factors` are flattened into strings before storing. This is critical because ChromaDB rejects nested dict metadata.

### 5. How do you verify it?

```bash
python -c "
from shared_functions import load_food_data, create_similarity_search_collection, populate_similarty_collection

food_items = load_food_data('data/FoodDataSet.json')
collection = create_similarity_search_collection('test_populate')
populate_similarty_collection(collection, food_items)
print('Collection populated successfully')
"
```

### 6. Avoiding duplicate population

The `create_similarity_search_collection()` function deletes any existing collection before creating a new one. This ensures you don't accidentally add items to a collection that already has data. Always recreate collections during development to avoid duplicates.

---

## 9. Phase 5 — Interactive Similarity Search

### 1. What are we learning?

**Semantic similarity search** — you provide a query (a sentence describing what you want), and ChromaDB finds the most similar documents.

How it works:

1. Your query text is converted to a vector (embedding) using the same embedding model.
2. ChromaDB compares this vector to all stored vectors.
3. It returns the `n_results` closest matches.
4. Each result includes the document text, metadata, and a **distance** value.
5. The **similarity score** is calculated as `1 - distance` (higher = more similar).

### 2. What are we building?

The `perform_similarity_search()` function handles retrieval:

```python
def perform_similarity_search(collection, query: str, n_results: int = 5) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=n_results)
    # Convert distance to similarity score
    similarity_score = 1 - results["distances"][0][i]
    # Format results into dictionaries
    return formatted_results
```

### 3. The Interactive Search Flow

```text
User query
    ↓
Query embedding (via embedding function)
    ↓
Vector similarity search (ChromaDB)
    ↓
Top N results
    ↓
Display results (name, description, match score)
```

### 4. The Interactive Chatbot

The `interactive_search.py` provides a command-line interface where users can type any food query and get instant results. It also suggests related searches based on cuisine types and average calories.

### 5. How do you verify it?

```bash
python -c "
from shared_functions import load_food_data, create_similarity_search_collection, populate_similarty_collection, perform_similarity_search

food_items = load_food_data('data/FoodDataSet.json')
collection = create_similarity_search_collection('test_interactive')
populate_similarty_collection(collection, food_items)
results = perform_similarity_search(collection, 'chocolate dessert', 3)
for r in results:
    print(f'{r[\"food_name\"]}: {r[\"similarity_score\"]*100:.1f}% match')
"
```

You should see chocolate-related food items ranked by similarity.

### 6. What should you understand?

- The embedding model understands that "chocolate dessert" is semantically related to "Chocolate Lava Cake" and "Chocolate Cake"
- The similarity score tells you how close the match is (0-100%)
- The order of results matters — the top result is the closest match
- Response time is typically under 0.1 seconds for hundreds of items

---

## 10. Phase 6 — Advanced Search with Metadata Filtering

### 1. What are we learning?

**Metadata filtering** lets you apply structured constraints on top of semantic results. ChromaDB supports a `where` clause with comparison operators:

| Operator | Meaning | Example |
|---|---|---|
| Exact match | `{"cuisine_type": "Indian"}` | Equal to value |
| Greater than or equal | `{"food_calories_per_serving": {"$gte": 400}}` | Greater than or equal |
| Less than or equal | `{"food_calories_per_serving": {"$lte": 500}}` | Less than or equal |
| In list | `{"cuisine_type": {"$in": ["Italian", "French"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |

### 2. What are we building?

The `perform_similarity_search_with_metadata()` function combines semantic search with filtering:

```python
def perform_similarity_search_with_metadata(
        collection, query: str, cuisine_filter: str | None = None,
        max_calories: int | None = None, n_results: int = 5) -> list[dict]:
    # Build where clause from filters
    filter_conditions = []
    if cuisine_filter:
        filter_conditions.append({"cuisine_type": cuisine_filter})
    if max_calories is not None:
        filter_conditions.append({"food_calories_per_serving": {"$lte": max_calories}})

    # Construct the where clause
    where_clause = filter_conditions[0] if len(filter_conditions) == 1 else {"$and": filter_conditions}

    # Perform combined search
    results = collection.query(query_texts=[query], where=where_clause, n_results=n_results)
    return formatted_results
```

### 3. Semantic Similarity vs. Structured Filtering

These are two fundamentally different operations:

| Operation | What it answers | How it works |
|---|---|---|
| **Semantic Similarity** | "What is conceptually similar?" | Embedding model compares meaning |
| **Metadata Filtering** | "What satisfies this constraint?" | Exact/range matching on structured fields |
| **Combined** | "Find similar items that also satisfy this constraint" | Both in a single query |

### 4. The Advanced Search Flow

```text
User query
    ↓
Semantic search (ChromaDB)
    ↓
Metadata filter (cuisine, calories)
    ↓
Combined results
    ↓
Display filtered results
```

### 5. The Advanced Search Interface

The `advanced_search.py` provides an interactive menu system with:
- Basic similarity search
- Cuisine-filtered search
- Calorie-filtered search
- Combined filters search
- Pre-defined demonstration queries

### 6. How do you verify it?

```bash
python -c "
from shared_functions import load_food_data, create_similarity_search_collection, populate_similarty_collection, perform_similarity_search_with_metadata

food_items = load_food_data('data/FoodDataSet.json')
collection = create_similarity_search_collection('test_advanced')
populate_similarty_collection(collection, food_items)

# Basic search
results = perform_similarity_search(collection, 'chocolate dessert', 3)
print(f'Basic search: {len(results)} results')

# Filtered search
results = perform_similarity_search_with_metadata(collection, 'chocolate dessert', cuisine_filter='Indian', n_results=2)
print(f'Filtered search: {len(results)} results')
"
```

### 7. What should you understand?

- Metadata filtering narrows results to items that satisfy structured constraints
- Combining semantic search with metadata filtering gives more precise results
- The `where` clause is applied *after* semantic similarity scoring
- The order of operations matters: semantic search first, then metadata filter

---

## 11. Phase 7 — RAG Chatbot

### 1. What are we learning?

**Retrieval-Augmented Generation (RAG)** is a technique where a language model's response is enhanced by retrieving relevant data from a knowledge base.

```text
User question
      ↓
Retrieve relevant foods (semantic search)
      ↓
Build context from search results
      ↓
Send context + question to LLM
      ↓
Generate recommendation
```

### 2. Why RAG instead of just asking an LLM?

An LLM like GPT or Gemini has general knowledge about food, but it:
- Doesn't know your specific food database
- Can hallucinate (make up food items that don't exist)
- Cannot provide accurate calorie counts or cuisine classifications

RAG solves this by:
1. **Retrieving** relevant food items from your database
2. **Providing** the retrieved data as context to the LLM
3. **Constraining** the LLM's response to the actual data

### 3. What are we building?

The RAG pipeline in `enhanced_rag_chatbot.py`:

```python
def generate_llm_rag_response(query: str, search_results: list[dict]) -> str:
    # Step 1: Prepare context from search results
    context = prepare_context_for_llm(query, search_results)

    # Step 2: Build the prompt with context
    prompt = f'''You are a helpful food recommendation assistant.

User Query: "{query}"

Retrieved Food Information:
{context}

Please provide a helpful, short response...

Response:'''

    # Step 3: Send to LLM
    generated_response = model.generate(prompt=prompt, params=None)

    # Step 4: Extract and return the response
    return generated_response["results"][0]["generated_text"]
```

### 4. How does it work?

1. **User asks a question** (e.g., "I want something sweet for dessert")
2. **The system retrieves** the top 3 most similar food items using semantic search
3. **The context is prepared** as a structured string with food names, descriptions, cuisine types, calories, etc.
4. **The prompt is built** with the user query and retrieved context
5. **The LLM generates** a conversational response based on the actual data
6. **A fallback response** is provided if the LLM fails

### 5. The RAG Flow

```text
User Query: "I want something sweet"
    ↓
Semantic Search → [Chocolate Cake, Chocolate Lava Cake, Apple Pie]
    ↓
Context Builder → Structured string with food details
    ↓
LLM Prompt → User query + retrieved context
    ↓
LLM Response → "I'd recommend Chocolate Lava Cake..."
```

### 6. How do you verify it?

The `system_comparison.py` script demonstrates the RAG chatbot's output:

```bash
python app/system_comparison.py
```

You should see the RAG chatbot generating a conversational response based on the retrieved food items.

### 7. What should you understand?

- RAG is not a magic solution — it requires good retrieval to work well
- The quality of the LLM response depends on the quality of the retrieved context
- The embedding model determines which items are retrieved
- Fallback responses handle cases where the LLM fails
- RAG is different from just querying an LLM because it uses your specific data

---

## 12. Phase 8 — Testing and Benchmarking

### 1. What are we learning?

**Testing vector database applications** — how do you verify that a semantic search system works correctly?

### 2. What are we building?

The `system_comparison.py` script provides a comprehensive benchmark:

```bash
python app/system_comparison.py
```

This tests all three systems with the same query ("chocolate dessert") and reports:
- Results for each system
- Response times for each system
- Comparison summary

### 3. What should you verify?

- **Correctness**: Does the search return relevant food items?
- **Performance**: Are response times reasonable (< 0.1 seconds)?
- **Filtering**: Does the advanced search correctly filter by cuisine and calories?
- **RAG**: Does the chatbot generate a coherent response based on retrieved data?

### 4. Expected Results

When searching for "chocolate dessert":
- **Interactive Search**: Returns chocolate-related items with similarity scores
- **Advanced Search**: Returns chocolate items + filtered Indian cuisine options
- **RAG Chatbot**: Generates a conversational recommendation

### 5. Benchmarking

```text
Interactive Search: ~0.035s
Advanced Search:    ~0.054s
RAG Chatbot:        ~0.032s
```

Response times vary based on system load and embedding model download status.

---

## 13. Phase 9 — Running All Three Systems

### 1. System Comparison

```bash
python app/system_comparison.py
```

This demonstrates all three systems side-by-side.

### 2. Interactive Search

```bash
python app/interactive_search.py
```

Provides a command-line chatbot interface. Type food queries and get results. Type `quit` to exit.

### 3. Advanced Search

```bash
python app/advanced_search.py
```

Provides an interactive menu system with filtering options.

### 4. RAG Chatbot

```bash
python app/enhanced_rag_chatbot.py
```

Provides a conversational chatbot with LLM integration. Requires IBM Watsonx.ai credentials.

### 5. What should you understand?

Each system demonstrates a different level of sophistication:

| System | Approach | Best For |
|---|---|---|
| Interactive Search | Direct semantic search | Simple, fast lookups |
| Advanced Search | Semantic + metadata filtering | Precise, constrained searches |
| RAG Chatbot | Retrieval + LLM generation | Conversational recommendations |

---

## 14. Architecture Overview

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `shared_functions.py` | Core functionality: data loading, collection creation, population, search |
| `interactive_search.py` | Interactive CLI chatbot for food search |
| `advanced_search.py` | Advanced search with filtering and interactive menus |
| `enhanced_rag_chatbot.py` | RAG chatbot with LLM integration |
| `system_comparison.py` | Side-by-side comparison of all three systems |

### Data Flow

```text
Food Dataset (JSON)
    ↓
load_food_data() — normalize and validate
    ↓
create_similarity_search_collection() — create ChromaDB collection with embedding function
    ↓
populate_similarty_collection() — add documents and metadata
    ↓
User Query
    ↓
perform_similarity_search() — semantic search
perform_similarity_search_with_metadata() — semantic search + filtering
    ↓
Results
    ↓
Display results (Interactive / Advanced)
Generate LLM response (RAG)
```

### Current Architecture (as implemented)

```text
shared_functions.py (core utilities)
    ├── load_food_data()
    ├── create_similarity_search_collection()
    ├── populate_similarty_collection()
    ├── perform_similarity_search()
    └── perform_similarity_search_with_metadata()

app/ (applications)
    ├── interactive_search.py
    ├── advanced_search.py
    ├── enhanced_rag_chatbot.py
    └── system_comparison.py
```

### Future Refactoring Opportunities

The current `shared_functions.py` consolidates all core functionality into a single module. Future improvements could separate concerns into distinct packages:

```text
data/
    loader.py          # load_food_data
embeddings/
    service.py         # embedding function setup
vector_store/
    chromadb_manager.py  # collection creation and population
retrieval/
    similarity.py      # perform_similarity_search
    filtering.py       # perform_similarity_search_with_metadata
rag/
    context.py         # prepare_context_for_llm
    generation.py      # generate_llm_rag_response
application/
    interactive.py     # interactive_search.py
    advanced.py        # advanced_search.py
    chatbot.py         # enhanced_rag_chatbot.py
    comparison.py      # system_comparison.py
```

This is a planned future improvement, not a current implementation.

---

## 15. Environment Variables

### Required Variables

The project uses a `.env` file for configuration. The `.env` file should contain:

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-v4-flash
```

> **Never commit your `.env` file to version control.** Add it to `.gitignore`.

### The `.env` file

The `.env` file is loaded by the system to configure the LLM connection. The `system_comparison.py` script does NOT require LLM configuration since it only demonstrates the first two systems.

---

## 16. ChromaDB `where` Filter Operators

| Operator | Meaning | Example |
|---|---|---|
| Exact match | `{"cuisine_type": "Indian"}` | Equal to value |
| Greater than or equal | `{"food_calories_per_serving": {"$gte": 400}}` | Greater than or equal |
| Less than or equal | `{"food_calories_per_serving": {"$lte": 500}}` | Less than or equal |
| In list | `{"cuisine_type": {"$in": ["Italian", "French"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |

---

## 17. Summary: Implemented vs. Future Work

### Implemented

- ✅ Food dataset loading and normalization
- ✅ ChromaDB collection creation with embedding function
- ✅ Semantic similarity search
- ✅ Metadata filtering (cuisine, calories)
- ✅ Interactive CLI chatbot
- ✅ Advanced search with filtering
- ✅ RAG chatbot with LLM integration
- ✅ System comparison tool
- ✅ Proper document/metadata distinction

### Known Issues

- `shared_functions.py` contains a typo in the function name (`populate_similarty_collection`) — this is a historical artifact that must be referenced when importing
- The `advanced_search.py` has its own `populate_similarity_collection` function that passes nested dictionaries as metadata, which ChromaDB rejects — use `shared_functions.py`'s `populate_similarty_collection` instead
- The `enhanced_rag_chatbot.py` has import issues with `advanced_search.populate_similarity_collection` and `ibm_watsonx_ai` dependencies
- The `system_comparison.py` has data path issues when run from different directories
- `system_comparison.py` calls `perform_filtered_similarity_search` which doesn't exist as a standalone function — use `perform_similarity_search_with_metadata` instead

### Optional Extensions (implement after completing the core lab)

- **Hybrid search** — combine keyword search with semantic search for better recall
- **Better filtering** — add taste profile, ingredient, and cooking method filters
- **Full dataset validation** — verify all 5081 food items load correctly
- **Personalization** — track user preferences and history
- **Conversation memory** — maintain context across multiple chatbot turns
- **Caching** — cache frequent queries and pre-compute embeddings
- **API** — wrap the system in a FastAPI/Flask backend
- **Docker** — containerize the application for easy deployment
- **Web UI** — add a Streamlit or Gradio web interface
- **PostgreSQL/pgvector** — replace ChromaDB with a persistent database
- **Evaluation** — add automated tests for retrieval quality
- **Image-based search** — allow uploading food photos for recommendations
- **Multilingual support** — support food queries in multiple languages
- **More advanced agentic behavior** — multi-step reasoning, tool use, planning

---

## 18. Quick Reference — Key Files and Functions

| File | Function / Class | Purpose |
|---|---|---|
| `shared_functions.py` | `load_food_data(file_path)` | Load and normalize food data from JSON |
| `shared_functions.py` | `create_similarity_search_collection(name, metadata)` | Create ChromaDB collection with embeddings |
| `shared_functions.py` | `populate_similarty_collection(collection, food_items)` | Populate collection with food data and embeddings |
| `shared_functions.py` | `perform_similarity_search(collection, query, n_results)` | Semantic similarity search |
| `shared_functions.py` | `perform_similarity_search_with_metadata(collection, query, cuisine_filter, max_calories, n_results)` | Semantic search with metadata filtering |
| `interactive_search.py` | `main()` | Interactive CLI food search chatbot |
| `advanced_search.py` | `main()` | Advanced search with filtering |
| `enhanced_rag_chatbot.py` | `main()` | RAG chatbot with LLM integration |
| `system_comparison.py` | `main()` | Side-by-side comparison of all three systems |

---

## 19. What You Learned

Here is a summary of the concepts and skills practiced:

- **Embeddings**: Text is converted into 384-dimensional vectors using `all-MiniLM-L6-v2`. Similar texts have similar vectors.
- **Vector databases**: ChromaDB stores vectors and finds similar vectors efficiently, enabling semantic search.
- **ChromaDB concepts**: Client, collection, documents, embeddings, metadata, IDs, querying.
- **Documents vs. metadata**: Documents are text for semantic similarity. Metadata is structured data for filtering.
- **Semantic search**: Provide a query text, get the most similar documents ordered by distance.
- **Metadata filtering**: Use ChromaDB's `where` expressions for structured filtering.
- **Combined search**: Semantic search and metadata filtering work together in a single `collection.query()` call.
- **RAG**: Retrieval-Augmented Generation combines vector search with LLM generation for data-aware conversations.
- **Data preparation**: Loading JSON, normalizing fields, handling nested structures, and ensuring metadata compatibility.
- **Data flow architecture**: Understanding how data flows from raw JSON through embeddings to search results.

---

## 20. Quick Start

```bash
# Install dependencies
pip install chromadb sentence-transformers torch

# Verify the system works
python app/system_comparison.py

# Try the interactive chatbot
python app/interactive_search.py

# Try the advanced search
python app/advanced_search.py

# Try the RAG chatbot (requires LLM setup)
python app/enhanced_rag_chatbot.py
```

---

## 21. Disclaimer / Learning Context

This is a practice/learning project developed while studying RAG and Agentic AI concepts through IBM's learning path. It is not officially developed, endorsed, or certified by IBM. The implementation reflects personal learning and experimentation with vector databases and retrieval-augmented generation.
