# Food Recommendation System

A hands-on learning project exploring the progression from traditional semantic similarity search to filtered retrieval and RAG-based conversational food recommendations using **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`).

This project is part of the IBM RAG and Agentic AI learning path. It demonstrates three approaches to food recommendation — from simple vector search to a full retrieval-augmented generation (RAG) pipeline.

---

## Project Overview

The project contains three food search systems of increasing sophistication:

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

### Implemented

- **Semantic similarity search** — find food by meaning using `all-MiniLM-L6-v2` embeddings (384 dimensions)
- **Metadata filtering** — filter results by cuisine type and calorie count using ChromaDB `where` clauses
- **Interactive CLI chatbot** — command-line interface for food search
- **Advanced search interface** — interactive menu system with filtering options
- **RAG pipeline** — retrieve relevant food items and generate conversational recommendations
- **System comparison** — side-by-side benchmark of all three approaches

---

## Technologies

Only libraries actually imported in the source code:

- **Python 3.10+**
- **chromadb** — vector database for all three systems
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dimensional embeddings with cosine distance
- **numpy** — numerical operations

Optional (for RAG chatbot):
- **ibm-watsonx** — IBM Granite LLM integration

---

## Dataset

The project uses `data/FoodDataSet.json`, containing **5081 food items** across multiple cuisines. Each record includes:

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
cd Food_Recommendation_System
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install chromadb sentence-transformers torch numpy
```

> **Note:** The `ibm_watsonx_ai` package is required for the RAG chatbot. Install with `pip install ibm-watsonx` if needed.

## Environment Variables

Create a `.env` file in the project root:

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-v4-flash
```

> **Never commit your `.env` file.** It is ignored by `.gitignore`.

---

## Running the Project

### System Comparison (all three systems)

```bash
cd app
python system_comparison.py
```

Tests all three systems with the query "chocolate dessert" and reports response times.

### Interactive Search Chatbot

```bash
cd app
python interactive_search.py
```

Type food queries and get instant results. Type `quit` to exit.

### Advanced Search Interface

```bash
cd app
python advanced_search.py
```

Interactive menu with basic search, cuisine filtering, calorie filtering, and combined filters.

### RAG Chatbot

```bash
cd app
python enhanced_rag_chatbot.py
```

Conversational chatbot with LLM integration. Requires LLM configuration in `.env`.

---

## Example Results

Running `system_comparison.py` with the query "chocolate dessert" produces:

```text
🔬 FOOD SEARCH SYSTEMS COMPARISON
==================================================
Successfully loaded 5081 food items from data/FoodDataSet.json

1️⃣ INTERACTIVE SEARCH APPROACH:
   1. Chocolate Lava Cake (61.9% match)
   2. Chocolate Cake (56.0% match)
   3. Chocolate Lava Cake (55.5% match)
⏱️ Response time: 0.035 seconds

2️⃣ ADVANCED SEARCH APPROACH:
   📋 Basic results: Chocolate Lava Cake, Chocolate Cake...
   🌶️ Filtered for Indian cuisine: Paneer Butter Masala, Chicken Dum Biryani
⏱️ Response time: 0.054 seconds

3️⃣ RAG CHATBOT APPROACH:
   🤖 Bot: Perfect! I found some excellent chocolate dessert options...
⏱️ Response time: 0.032 seconds
```

> **Note:** Results may vary depending on system load, embedding model cache status, and ChromaDB version. These are local run results, not formal benchmarks.

---

## Project Structure

```text
Food_Recommendation_System/
├── .env                     # LLM configuration (never committed)
├── .gitignore               # Git ignore rules
├── PLAN.md                  # Learning lab plan
├── README.md                # This file
├── data/
│   └── FoodDataSet.json     # Food dataset (5081 items)
└── app/
    ├── __pycache__/         # Python bytecode (not committed)
    ├── shared_functions.py  # Core functions: data loading, collection creation, search
    ├── interactive_search.py     # Interactive CLI chatbot
    ├── advanced_search.py        # Advanced search with filtering
    ├── enhanced_rag_chatbot.py   # RAG chatbot with LLM
    └── system_comparison.py      # Side-by-side comparison
```

---

## Learning Roadmap

See **[PLAN.md](PLAN.md)** for a detailed step-by-step learning lab that covers:

1. Preparing the Dataset
2. Understanding Embeddings
3. Setting Up ChromaDB
4. Generating Embeddings
5. Interactive Similarity Search
6. Advanced Search with Metadata Filtering
7. RAG Chatbot
8. Testing and Benchmarking
9. Running All Three Systems

---

## Future Improvements

The following features are **planned but not yet implemented**:

- Hybrid search (keyword + semantic)
- More advanced filtering (taste profile, ingredients, cooking method)
- Full dataset validation (all 5081 items)
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

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"cuisine_type": "Indian"}` | Equal to value |
| Greater than or equal | `{"food_calories_per_serving": {"$gte": 400}}` | Greater than or equal |
| Less than or equal | `{"food_calories_per_serving": {"$lte": 500}}` | Less than or equal |
| In list | `{"cuisine_type": {"$in": ["Italian", "French"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |

---

## Disclaimer / Learning Context

This is a practice/learning project developed while studying RAG and Agentic AI concepts through IBM's learning path. It is not officially developed, endorsed, or certified by IBM. The implementation reflects personal learning and experimentation with vector databases and retrieval-augmented generation.
