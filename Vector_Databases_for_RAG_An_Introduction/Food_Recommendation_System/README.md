# Food Recommendation System

A hands-on learning project exploring the progression from traditional semantic similarity search to filtered retrieval and RAG-based conversational food recommendations using **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`).

**Status: Experimental lab implementation; execution blockers remain.** [Course 3](../README.md) · [Certificate](../../README.md)

This project is part of the IBM RAG and Agentic AI learning path. It demonstrates three approaches to food recommendation — from simple vector search to a full retrieval-augmented generation (RAG) pipeline.

---

## Project Overview

The source contains three approaches of increasing sophistication. Their presence does not imply that every entry point currently completes successfully; see [Known Implementation Limitations](#known-implementation-limitations).

| System | Approach | Description |
|---|---|---|
| **Interactive Search** | Semantic similarity search | Fast, direct food lookup by meaning |
| **Advanced Search** | Semantic search + metadata filtering | Precise control with cuisine and calorie filters |
| **RAG Chatbot** | Retrieval-Augmented Generation | Conversational recommendations powered by an LLM |

---

## Architecture

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

## Features

### Present in Source

- **Semantic similarity search** — find food by meaning using `all-MiniLM-L6-v2` embeddings (384 dimensions)
- **Metadata filtering** — filter results by cuisine type and calorie count using ChromaDB `where` clauses
- **Interactive CLI chatbot** — command-line interface for food search with search history
- **Advanced search interface** — interactive menu system with filtering options
- **Calorie budget checker** — interactive tool to find foods within a calorie budget
- **Result limiter** — tool to test how different result limits affect search quality
- **RAG pipeline** — retrieve relevant food items and generate conversational recommendations
- **System comparison** — a demonstration of three response styles; its "RAG" response is formatted in Python and does not call an LLM

---

## Technologies

Only libraries actually imported in the source code:

- **Python 3.10+**
- **chromadb** — vector database for all three systems
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dimensional embeddings; the collection metric is not explicitly configured

Optional (for RAG chatbot):
- **ibm-watsonx-ai** — `ModelInference` integration with `ibm/granite-4-h-small`

---

## Dataset

The committed [`data/FoodDataSet.json`](data/FoodDataSet.json) contains **185 food records** across multiple cuisines. This is the count of the tracked JSON array, not the size of a separate upstream dataset. Each record includes:

| Field | Description |
|---|---|
| `food_id` | Unique identifier |
| `food_name` | Name of the dish |
| `food_description` | Description of the dish |
| `food_calories_per_serving` | Calories per serving |
| `food_nutritional_factors` | Nutritional info (carbs, protein, fat) |
| `food_ingredients` | List of ingredients |
| `food_health_benefits` | Health benefits description |
| `cooking_method` | How it's cooked |
| `cuisine_type` | Cuisine classification |
| `food_features` | Taste, texture, appearance features |

The data loading function normalizes all records and extracts taste profiles from nested `food_features` dictionaries.

---

## How It Works

### Interactive Search

```text
User query ("chocolate dessert")
    ↓
Query embedding (via all-MiniLM-L6-v2)
    ↓
Vector similarity search (ChromaDB)
    ↓
Top 3 results
    ↓
Display with similarity scores
```

### Advanced Search

```text
User query
    ↓
Semantic search + metadata filter
    ↓
ChromaDB query with where clause
    ↓
Filtered results (cuisine, calories)
```

### RAG Chatbot

```text
User question
    ↓
Retrieve relevant foods (semantic search)
    ↓
Build context from search results
    ↓
Send context + question to LLM
    ↓
Generate conversational recommendation
```

---

## Installation

**Requirements:** Python 3.10+, internet access for downloading the embedding model on first run.

```bash
cd Vector_Databases_for_RAG_An_Introduction/Food_Recommendation_System
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install chromadb sentence-transformers torch
```

> No dependency manifest is tracked. The RAG source additionally imports `ibm_watsonx_ai`, provided by `ibm-watsonx-ai`. Its fixed Skills Network authentication and the source blockers below prevent this from being a portable local RAG setup.

## Environment Variables

The tracked Python source reads **no environment variables** and does not load
`.env`. `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` do not configure this project.
`enhanced_rag_chatbot.py` fixes the watsonx URL, `project_id="skills-network"`, and
model ID in code, without a normal local API-key configuration path.

---

## Running the Project

The entries below identify real source entry points and the working directory
needed for their existing dataset-path assumptions. They are **not successful
execution results**; several require the code corrections listed below.

| Entry point | Working directory (within this project) | Invocation | Role |
|---|---|---|---|
| `app/interactive_search.py` | Project root | `python app/interactive_search.py` | Semantic CLI with history |
| `app/system_comparison.py` | Project root | `python app/system_comparison.py` | Response-style/timing demonstration, no live LLM |
| `app/calorie_checker.py` | `data` | `python ../app/calorie_checker.py` | Calorie-budget exercise |
| `app/result_limiter.py` | `data` | `python ../app/result_limiter.py` | Result-limit exercise |
| `app/advanced_search.py` | `data` | `python ../app/advanced_search.py` | Filtering menu; missing helper and metadata mismatch |
| `app/enhanced_rag_chatbot.py` | `data` | `python ../app/enhanced_rag_chatbot.py` | watsonx RAG experiment; unresolved annotation/configuration |

### System Comparison (all three systems)

The comparison script queries three collections with "chocolate dessert" and reports timings. Its third response is assembled from retrieved fields in Python, so those timings are not LLM/RAG latency measurements.

### Calorie Checker

Interactive tool that asks for a calorie budget, then searches for foods within that budget using metadata filtering. Shows which foods fit and which are over budget.

### Result Limiter

Tool to test how different result limits affect search quality. Compares results for limits of 1, 3, 5, and 10, and allows interactive testing with custom queries.

### Interactive Search Chatbot

Provides a command-line chatbot interface. Type food queries and get instant results. Type `history` to view the last 10 searches. Type `quit` to exit.

### Advanced Search Interface

Interactive menu with basic search, cuisine filtering, calorie filtering, and combined filters.

### RAG Chatbot

Conversational RAG source with watsonx integration. It is not configured by `.env` and currently has the blockers below.

---

## Known Implementation Limitations

- **Dataset paths differ.** Interactive search and comparison use `data/FoodDataSet.json`; the other scripts use `FoodDataSet.json`. Running everything from `app/` does not resolve the committed dataset.
- **Metadata contracts differ.** `shared_functions.py` stores `name`, `description`, and `calories`; the advanced population helper retains original dataset keys. Shared result formatting expects the former names. Nested dictionaries in advanced metadata also need normalization for Chroma's supported value types.
- **Calorie-filter mismatch.** The shared filter helper queries `food_calories_per_serving`, while shared ingestion stores `calories`; calorie filtering is therefore not reliable as written.
- **Missing helper.** `advanced_search.py` calls `perform_filtered_similarity_search`, but no tracked definition exists; the shared function is named `perform_similarity_search_with_metadata`.
- **RAG import-time blocker.** `enhanced_rag_chatbot.py` annotates `conversation_history` with `List[str]` without importing `List`, and initializes a Skills Network model at import time.
- **Similarity scores are heuristic.** `1 - distance` is presented as a percentage even though cosine distance is not configured. It is not a calibrated relevance probability.
- No automated test suite or validated benchmark is committed. The comparison's response formatting is not proof of hosted-LLM generation.

---

## Project Structure

```text
Food_Recommendation_System/
├── .gitignore               # Git ignore rules
├── PLAN.md                  # Learning lab plan
├── README.md                # This file
├── data/
│   └── FoodDataSet.json     # Committed food dataset (185 records)
└── app/
    ├── shared_functions.py  # Core functions: data loading, collection creation, search
    ├── interactive_search.py     # Interactive CLI chatbot with search history
    ├── advanced_search.py        # Advanced search with filtering
    ├── enhanced_rag_chatbot.py   # RAG chatbot with LLM
    ├── system_comparison.py      # Side-by-side comparison
    ├── calorie_checker.py        # Interactive calorie budget checker
    └── result_limiter.py         # Result limit testing tool
```

---

## Learning Roadmap

See **[PLAN.md](PLAN.md)** for a detailed step-by-step learning lab that covers:

The retained plan is a lab roadmap with historical examples, not an authoritative
record of the current dataset size, measured timings, or completed functionality.
Use the tracked JSON and source limitations above for the current implementation.

1. Preparing the Dataset
2. Understanding Embeddings
3. Setting Up ChromaDB
4. Generating Embeddings
5. Interactive Similarity Search
6. Advanced Search with Metadata Filtering
7. RAG Chatbot
8. Testing and Benchmarking
9. Running All Three Systems
10. Calorie Budget Checker
11. Result Limiter Tool

---

## Future Improvements

The following features are **planned but not yet implemented**:

- Hybrid search (keyword + semantic)
- More advanced filtering (taste profile, ingredients, cooking method)
- Full dataset validation and consistent ingestion/filter/result contracts for the 185 committed records
- Personalization and user preference learning
- Conversation memory for multi-turn dialogue
- Query caching and pre-computed embeddings
- FastAPI/Flask REST API
- Docker containerization
- Web UI (Streamlit/Gradio)
- PostgreSQL/pgvector for persistent storage
- Automated evaluation metrics
- Image-based food search
- Multilingual support
- Advanced agentic behavior (tool use, planning)

See **[PLAN.md](PLAN.md)** for detailed descriptions.

---

## ChromaDB `where` Filter Operators

These reference examples use the **shared ingestion schema** (`calories`). The
current calorie helper still queries the inconsistent original field name, as
documented above; the examples do not imply that helper is fixed.

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"cuisine_type": "Indian"}` | Equal to value |
| Greater than or equal | `{"calories": {"$gte": 400}}` | Greater than or equal |
| Less than or equal | `{"calories": {"$lte": 500}}` | Less than or equal |
| In list | `{"cuisine_type": {"$in": ["Italian", "French"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |

---

## Disclaimer / Learning Context

This is a practice/learning project developed while studying RAG and Agentic AI concepts through IBM's learning path. It is not officially developed, endorsed, or certified by IBM. The implementation reflects personal learning and experimentation with vector databases and retrieval-augmented generation.
