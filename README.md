# IBM RAG and Agentic AI Professional Certificate

> All projects listed here are both IBM practical labs and self-build projects as practice on what I learn through the program.

---

## About the Program

**IBM RAG and Agentic AI Professional Certificate** — a 10-course specialization on Coursera by IBM Skills Network.

> Build real-world AI with RAG and agentic AI. Use AI tools to streamline automation, drive innovation & take your career further, faster.

**Instructors:** IBM Skills Network Team (Wojciech 'Victor' Fulmyk, Ricky Shi)

**Program stats:** 10-course series · 4.6 rating (1,126 reviews) · 105,310+ enrolled · Advanced level · Flexible schedule (8 weeks at 3 hours/week)

---

## What You'll Learn

- Build job-aligned GenAI skills and hands-on experience to create RAG, multimodal, and agentic AI applications employers need
- Design and chain AI tools with LangChain for modular, reusable gen AI workflows
- Implement function calling, RAG, and vector stores to build intelligent, context-aware applications
- Create autonomous AI agents using LangGraph, CrewAI, and AG2 for real-world impact

## Skills You'll Gain

AI Security · AI Integrations · Retrieval-Augmented Generation · Software Development · Generative AI Agents · Agentic systems · LLM Application · Multimodal Prompts · Prompt Patterns · Tool Calling · Vector Databases · Generative AI · AI Workflows · Model Context Protocol · Agentic Workflows · OpenAI API · Prompt Engineering · LangGraph · AI Orchestration · LangChain · AI Agents · Agentic Workflows

---

## Courses in the Program

| # | Course | Duration | Status |
|---|---|---|---|
| 1 | Develop Generative AI Applications: Get Started | 10 hours | **Completed** |
| 2 | Build RAG Applications: Get Started | 7 hours | **Completed** |
| 3 | Vector Databases for RAG: An Introduction | 9 hours | **Completed** |
| 4 | Advanced RAG with Vector Databases and Retrievers | 8 hours | Not Started |
| 5 | Build Multimodal Generative AI Applications | 8 hours | Not Started |
| 6 | Fundamentals of Building AI Agents | 11 hours | Not Started |
| 7 | Agentic AI with LangChain and LangGraph | 11 hours | Not Started |
| 8 | Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI | 13 hours | Not Started |
| 9 | Build AI Agents using MCP | 10 hours | Not Started |
| 10 | RAG and Agentic AI Capstone Project | 14 hours | Not Started |

---

## What This Repository Contains

This repository contains my hands-on work while completing the IBM RAG and Agentic AI Professional Certificate. It is an engineering learning portfolio — I work through each course's guided labs, then rebuild them from scratch and extend them, swapping the proprietary IBM watsonx.ai stack for free alternatives (OpenRouter + local Hugging Face models) so everything runs on a normal machine.

The goal is a practical, working understanding of:

- LLM applications and prompt engineering
- LangChain (LCEL, chains, structured output)
- Retrieval-Augmented Generation (RAG)
- Embeddings and vector databases
- AI agents, agentic workflows, and multi-agent systems
- MCP and related agent infrastructure

---

## Course Summaries

### Course 1 — Develop Generative AI Applications: Get Started

IBM's course focuses on the fundamentals of building generative AI applications: LLM APIs, prompt templates, few-shot prompting, LangChain chains (LCEL), and forcing models to produce structured output. The guided project is a Flask + LangChain app that returns structured JSON instead of free text.

**Repository work** — I rebuilt the guided project and then built two more applications in the same style, all using OpenRouter instead of watsonx.ai:

- **GenAI Flask App** (`Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App/`) — the course guided project rebuilt: type a message, pick a model (Llama / Granite / Mistral), get back a validated JSON response (`summary`, `sentiment`, `response`). A single shared `ChatPromptTemplate` + `JsonOutputParser` pipe replaced the course's three per-model raw-text templates. Includes a Flask-free CLI sanity check (`llm_test.py`).
- **AI Email Assistant** (`Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant/`) — generates polished emails (subject + body + improvement suggestions) as structured JSON. Adds a **Compare All** mode that runs the same prompt across four models in parallel and shows per-model latency, length, and a subject-quality score. Modular layout: `config` / `model` / `parser` / `prompts` / `services`. The detailed build log in `plan.md` documents real bugs I hit (wrong OpenRouter base URL causing DNS failures, intermittent `OutputParserException` on markdown-wrapped JSON, dependency drift between langchain versions).
- **Book/Movie Advisor** (`Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor/`) — takes a free-text mood and returns exactly 3 structured recommendation cards via a Pydantic `RecommendationList` schema. Selectable among a configurable set of OpenRouter models.

See [`Develop_Generative_AI_Applications_Get_Started/README.md`](Develop_Generative_AI_Applications_Get_Started/README.md) for the full course-level overview.

**Key things learned**

- LCEL pipe chains: `prompt | llm | parser` is a runnable, testable unit.
- Structured output: Pydantic schema + `JsonOutputParser` converts free-text model output into validated Python dicts; format instructions get injected into the prompt.
- Prompt engineering: reusable `PromptTemplate`s with input vs. partial variables, few-shot examples, and JSON-literal escaping (`{{ }}`).
- Why chat-completions APIs (OpenAI/OpenRouter) eliminate per-model special-token templates.
- Debugging order for LLM apps: key present → provider reachable → chain direct call → Flask → UI.

---

### Course 2 — Build RAG Applications: Get Started

IBM's course introduces RAG: document loading, chunking/splitting, embeddings, vector stores, retrieval, similarity search, and query engines — taught through LlamaIndex and Gradio. The progression is from a plain LLM app toward a retrieval-augmented one.

**Repository work**

- **LinkedIn Icebreaker Bot** (`Build_RAG_Applications_Get_Started/icebreaker/`) — a from-scratch rebuild of the course's LlamaIndex lab, with the provider swapped from watsonx to **OpenRouter (LLM) + local Hugging Face embeddings** (`sentence-transformers/all-MiniLM-L6-v2`, free and offline). A complete RAG pipeline built file-by-file:
  - `modules/data_extraction.py` — profile data loading (mock JSON or the discontinued ProxyCurl API).
  - `modules/data_processing.py` — `SentenceSplitter` chunking, `VectorStoreIndex` construction, and an embedding-integrity check.
  - `modules/query_engine.py` — generation via a LlamaIndex query engine, plus a **hand-written retrieval** path (`as_retriever()` → top-k nodes → context assembly) to expose every RAG stage explicitly.
  - `main.py` (CLI) and `app.py` (Gradio UI with runtime model switching and per-session indexes).
  - A detailed `PLAN.md` walking through the build, and the pinned `requirements.txt` (`llama-index-core 0.14.x`).
- **Personal Branding Agent** (`Build_RAG_Applications_Get_Started/PersonalBrandingAgent/`) — a production-oriented extension of the course's RAG material. The **knowledge base** (a structured `data/` corpus) and the **LinkedIn OAuth integration** are complete; the ingest → retrieve → generate → evaluate → publish pipeline is defined in `PLAN.md` (10 phases) and being built incrementally.
  - `data/` — structured personal knowledge base with 9 data categories and evidence state tracking
  - `Auth_handling/` — LinkedIn OAuth 2.0 flow with token refresh and post publishing via the LinkedIn REST API
  - `docs/` — architecture docs, phase docs, ADRs
  - `RAG_Lab.ipynb` — completed IBM course RAG notebook (reference)
- **Gradio demos** (`Build_RAG_Applications_Get_Started/Gradio/`) — a `gr.Interface` sentence builder and a transformers/torchvision image-captioning demo, for Gradio UI practice.

See [`Build_RAG_Applications_Get_Started/README.md`](Build_RAG_Applications_Get_Started/README.md) for the full course-level overview.

**Key things learned**

- The RAG pipeline as a loop: load → split → embed → store → index → retrieve → generate.
- Chunking matters: `chunk_size`/`chunk_overlap` trade-offs and sentence-boundary splitting.
- Embeddings turn text into vectors so similarity search can be semantic, not keyword-based.
- LlamaIndex's `VectorStoreIndex`/`as_query_engine` hides retrieval; `as_retriever()` exposes it — good for learning what the abstraction is doing.
- Retrieval quality is upstream of generation quality: garbage in → grounded-but-wrong answers out.
- Provider-agnostic frameworks mean swapping watsonx for OpenRouter only touches the factory files.

---

### Course 3 — Vector Databases for RAG: An Introduction

IBM's course teaches vector databases from the inside out: how embeddings become vector representations, vector collections, adding/updating/deleting documents, similarity search, and distance metrics — with hands-on ChromaDB labs.

**Repository work** — three projects demonstrating semantic search with metadata filtering:

- **Books Advanced Search** (`Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search/`) — a modular Python application storing 8 book records in ChromaDB with layered architecture (data → documents → vector_store → repository → search service). Four search exercises: similarity search, genre filtering (`$in`), rating filtering (`$gte`), combined semantic + metadata search. Persistent ChromaDB storage via `chromadb.PersistentClient`.
- **Job Description Matcher** (`Vector_Databases_for_RAG_An_Introduction/job_description_matcher/`) — stores ~30 job descriptions in ChromaDB with rich metadata, enables semantic search with metadata filtering, and includes evaluation metrics (Hit@K, Precision@K).
- **Similarity Search on Employee Records** (`Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records/`) — employee similarity search with metadata filtering using department, experience, location, and combined semantic + metadata queries.

See [`Vector_Databases_for_RAG_An_Introduction/README.md`](Vector_Databases_for_RAG_An_Introduction/README.md) for the full course-level overview.

**Key concepts practiced**

- ChromaDB collections — creating, ingesting, and querying a persistent vector store
- SentenceTransformer embeddings — converting text to vectors with `SentenceTransformerEmbeddingFunction`
- Cosine distance — 0 = identical, 1 = opposite
- Metadata filtering — `where` clauses with `$in`, `$gte`, `$lte`, `$and`, `$or`
- Combined search — `where` in `collection.query()` to filter semantic results
- Document construction — combining multiple fields into effective searchable text strings

---

### Courses 4–10 (Not Started)

| # | Course | Focus |
|---|---|---|
| 4 | Advanced RAG with Vector Databases and Retrievers | Reranking, hybrid search, advanced retrievers |
| 5 | Build Multimodal Generative AI Applications | Text + image models, vision applications |
| 6 | Fundamentals of Building AI Agents | Agent loops, tool calling, agent design patterns |
| 7 | Agentic AI with LangChain and LangGraph | Workflow graphs, state, tool use in LangGraph |
| 8 | Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI | Multi-agent frameworks and orchestration |
| 9 | Build AI Agents using MCP | Model Context Protocol, FastMCP, tool servers |
| 10 | RAG and Agentic AI Capstone Project | Full end-to-end agentic RAG project |

None of these have been started. No projects for these courses exist in the repository yet.

---

## Technical Skills

Only technologies actually used in this repository are listed as demonstrated.

### LLM Application Development

- Python 3.10+
- LLM APIs via **OpenRouter** (OpenAI-compatible chat-completions), with runtime model switching
- Prompt engineering: `PromptTemplate`, few-shot examples, system prompts, partial vs. input variables
- Structured outputs: Pydantic schemas + LangChain `JsonOutputParser`
- LangChain **LCEL** chains (`prompt | llm | parser`)
- Flask web apps (routes, JSON APIs, template rendering)
- Multi-model experimentation and side-by-side comparison (latency, length, quality scoring)
- Vanilla JS/CSS frontends with `fetch` and XSS-safe rendering

### RAG

- Full RAG pipeline: load → split → embed → store → retrieve → generate
- Document loading (`TextLoader`) and chunking (`CharacterTextSplitter`, `SentenceSplitter`)
- Embeddings via local Hugging Face `sentence-transformers` (`all-MiniLM-L6-v2`)
- LlamaIndex: `VectorStoreIndex`, `SentenceSplitter`, query engines, retrievers
- Retrieval chains: `RetrievalQA`, `ConversationBufferMemory`, `ConversationalRetrievalChain`
- Grounded prompting ("use only the information provided in the context")
- Manual retrieval with explicit top-k node assembly

### Vector Databases

- **ChromaDB** — collections, CRUD, persistence, `query()` with `where` filters
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dim embeddings, cosine distance
- Embedding verification (checking every node got a non-null vector)

### LinkedIn Integration (applied in the Personal Branding Agent)

- LinkedIn OAuth 2.0 flow (authorization code → tokens, refresh handling)
- Publishing posts via the LinkedIn REST API (`/rest/posts`, `userinfo`, `w_member_social` scope)

### Coming Later in the Certificate

Technologies from the certificate syllabus that are **not yet demonstrated** in this repository: FAISS, LangGraph, CrewAI, AutoGen/AG2, BeeAI, MCP/FastMCP, advanced retrieval/reranking, multimodal models, AI evaluation frameworks, and AI security.

---

## Projects and Experiments

### GenAI Flask App — structured JSON output via LCEL

A Flask app where you type a message and receive a validated JSON object (`summary`, `sentiment` 0–100, `response`) from a selectable model. Rebuild of the IBM guided project, with watsonx swapped for OpenRouter.

**Concepts:** prompt templates, LCEL chains, structured output, provider abstraction.
**Technologies:** Flask, LangChain (`ChatPromptTemplate`, `JsonOutputParser`), Pydantic, OpenRouter.

### AI Email Assistant — multi-model generation + comparison

Generates complete emails (subject, body, tone, improvement suggestions) as structured JSON, with a **Compare All** mode that generates the same email with four models in parallel and renders per-model cards with time, length, and a subject-quality heuristic.

**Concepts:** few-shot prompting for JSON, model evaluation (latency/length/quality), parallel frontend fan-out, XSS-safe rendering.
**Technologies:** Flask, LangChain LCEL, Pydantic, OpenRouter, vanilla JS (`Promise.all`).

### Book/Movie Advisor — structured recommendation generation

Free-text mood → exactly 3 recommendation cards, validated by a nested Pydantic schema (`RecommendationList`), with a configurable model dropdown.

**Concepts:** nested structured output, `Literal` type constraints, few-shot format locking.
**Technologies:** Flask, LangChain, Pydantic, OpenRouter.

### LinkedIn Icebreaker Bot — a RAG app built from scratch

A complete LlamaIndex RAG application rebuilt from the course lab: load a LinkedIn profile, chunk it, embed it with a local model, index it, and answer questions with grounded facts via an OpenRouter LLM. CLI and Gradio UIs.

**Concepts:** full RAG pipeline, sentence splitting, semantic retrieval, grounding, provider-agnostic design.
**Technologies:** LlamaIndex (core 0.14.x), `llama-index-llms-openrouter`, `llama-index-embeddings-huggingface`, `sentence-transformers`, Gradio.

### Personal Branding Agent — RAG applied to a real project (in progress)

A production-oriented agent that generates, evaluates, and publishes authentic LinkedIn posts grounded in a personal knowledge base. Currently the **knowledge base** (a structured `data/` corpus: completed/in-progress projects, courses, certificates, evidence with evidence states, stories/lessons, vision, writing style, positioning) and the **LinkedIn OAuth integration** are done; the ingest → retrieve → generate → evaluate → publish pipeline is **planned but not yet built** (`PLAN.md` defines 10 phases).

**Concepts:** evidence-grounded generation, deterministic agent workflows with quality gates (PASS / REVISE / REJECT), metadata-aware retrieval, human-in-the-loop publishing, audit trails.
**Technologies:** LangChain + Chroma (planned), `sentence-transformers`, OpenRouter, Flask (planned), LinkedIn OAuth (`Auth_handling/`).

### Gradio experiments

A sentence-builder `gr.Interface` (sliders, dropdowns, checkboxes) and a transformers/torchvision image demo — hands-on practice with Gradio's component model.

**Concepts:** Gradio interfaces, image preprocessing (resize/crop/normalize), Hugging Face model inference.
**Technologies:** Gradio, transformers, torch.

### Books Advanced Search — semantic search with ChromaDB

Modular ChromaDB application with layered architecture. Four exercises: similarity search, genre filtering, rating filtering, combined semantic + metadata search.

**Concepts:** ChromaDB collections, embeddings, cosine distance, metadata filtering, separation of concerns.
**Technologies:** ChromaDB, `sentence-transformers` (`all-MiniLM-L6-v2`).

### Job Description Matcher — semantic search with evaluation

Semantic job search with ~30 records, metadata filtering, and evaluation metrics (Hit@K, Precision@K).

**Concepts:** ChromaDB query with `where`, evaluation metrics, search experimentation.
**Technologies:** ChromaDB, `sentence-transformers`.

### Similarity Search on Employee Records — ChromaDB fundamentals

Employee similarity search demonstrating pure similarity search, metadata filtering, and combined semantic + metadata queries.

**Concepts:** ChromaDB `query()` and `get()`, cosine distance, metadata operators.
**Technologies:** ChromaDB, `sentence-transformers`.

---

## What I'm Learning

Practical engineering lessons emerging from the completed courses:

- **LLM apps are probabilistic + deterministic.** The pattern `prompt → model → parser → validated dict` means one uncontrolled, probabilistic call sandwiched between deterministic glue (input validation, output parsing, HTTP). Design for that: parse and validate everything, treat model output as untrusted.
- **Why RAG is needed.** Models know nothing about your data unless you put it in the prompt. RAG is the discipline of retrieving the right context and stuffing it into the prompt so answers are grounded and current.
- **Embeddings capture meaning.** Similar sentences get similar vectors, which is what makes semantic (vs. keyword) search possible — and why chunk quality directly affects retrieval quality.
- **Chunking is a real design decision.** Chunk size, overlap, and splitting strategy determine whether a question can find its answer in one retrieved chunk.
- **Retrieval quality limits generation quality.** A strong retriever with a weak generator beats a weak retriever with a strong generator.
- **Frameworks are abstractions over a small set of ideas.** LlamaIndex's query engine wraps "embed query → find top-k → build context → call LLM." LangChain's LCEL is `prompt | model | parser`. Understanding the underlying steps makes framework choices (and swaps) easy.
- **Providers are swappable.** Because everything goes through OpenAI-compatible APIs, swapping watsonx for OpenRouter never touched RAG logic — only config and factory files.
- **Debugging order matters.** Key → network → chain directly → Flask → UI isolates failures quickly (and saved me real hours on the base-URL bug).

---

## Relationship to My AI Engineering Work

This IBM repository is one part of a broader progression toward AI engineering. In parallel, I maintain a **separate repository focused on building AI agents from scratch**, where I implement the underlying mechanics directly:

- agent loops (call LLM → parse → execute tools → repeat)
- decorator-based tool registries and tool schemas
- tool calling (OpenAI-style `tool_calls` protocol)
- lightweight multi-agent orchestration and routing
- deterministic validation and Judge/Critic evaluation

The two repositories are **complementary, not integrated**:

- **IBM repository** → learning established AI application patterns and frameworks (LangChain, LlamaIndex, RAG, and later LangGraph, CrewAI, MCP) the way the industry actually uses them.
- **AI-Agents repository** → understanding the same ideas from first principles, without frameworks.

Together they represent:

```
Understand the abstractions
          ↓
Understand what is underneath them
          ↓
Learn when to use each approach
          ↓
Build production-oriented AI systems
```

---

## Repository Structure

```text
IBM/
├── Develop_Generative_AI_Applications_Get_Started/    # Course 1 — COMPLETED
│   ├── GenAI_Flask_App/                             # Flask + LangChain structured JSON output
│   ├── AI_Email_Assistant/                          # multi-model email generator + Compare All
│   └── Book_Movie_Advisor/                          # mood → structured recommendations
├── Build_RAG_Applications_Get_Started/                # Course 2 — COMPLETED
│   ├── icebreaker/                                  # LlamaIndex RAG app (CLI + Gradio)
│   ├── PersonalBrandingAgent/                       # RAG + LinkedIn OAuth agent (in progress)
│   │   ├── data/                                    # structured personal knowledge base
│   │   ├── Auth_handling/                           # LinkedIn OAuth + publish scripts
│   │   ├── docs/                                    # architecture / phases / evaluation / ADRs
│   │   ├── PLAN.md                                  # 10-phase roadmap
│   │   └── RAG_Lab.ipynb                            # completed course RAG notebook
│   └── Gradio/                                      # Gradio UI practice demos
├── Vector_Databases_for_RAG_An_Introduction/          # Course 3 — COMPLETED
│   ├── Books_Advanced_Search/                       # ChromaDB semantic book search
│   ├── job_description_matcher/                     # Job description semantic search + evaluation
│   └── Similarity_Search_on_Employee_Records/       # Employee similarity search
├── .env.example                                     # OPENROUTER_API_KEY=your_key_here
├── .gitignore                                       # .env, venvs, __pycache__
└── README.md                                        # this file
```

---

## Setup

Each project is self-contained with its own `requirements.txt` and uses environment variables for secrets. **Never commit `.env` files.**

1. Create and activate a virtual environment in the project directory:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your local `.env` from the project's `.env.example` and fill in keys:

```bash
cp .env.example .env
```

### Environment variables used by the projects

| Project | Variables |
|---|---|
| `Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App/` | `OPENROUTER_API_KEY`, optional `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME` |
| `Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant/` | `OPENROUTER_API_KEY` |
| `Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor/` | `OPENROUTER_API_KEY` |
| `Build_RAG_Applications_Get_Started/icebreaker/` | `OPENROUTER_API_KEY`, optional `LLM_MODEL_ID` |
| `Build_RAG_Applications_Get_Started/PersonalBrandingAgent/` | `OPENAI_API_KEY` (OpenRouter key per its `config.py`), `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` |
| `Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search/` | None required |
| `Vector_Databases_for_RAG_An_Introduction/job_description_matcher/` | None required |
| `Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records/` | None required |

> Example: `OPENROUTER_API_KEY=your_key_here` — get a free key at <https://openrouter.ai/keys>.

### Running the apps

```bash
# Course 1 — Flask apps (default port 5000)
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App && python llm_test.py   # sanity check, no Flask
cd Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App && python app.py         # chat UI
cd Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant && python app.py      # email generator
cd Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor && python app.py      # recommender

# Course 2 — Icebreaker (LlamaIndex RAG)
cd Build_RAG_Applications_Get_Started/icebreaker && python main.py --mock      # CLI with mock data
cd Build_RAG_Applications_Get_Started/icebreaker && python app.py              # Gradio UI (port 7860)

# Course 2 — Gradio demos
cd Build_RAG_Applications_Get_Started/Gradio && python app.py                  # sentence builder (port 7860)
cd Build_RAG_Applications_Get_Started/Gradio && python main.py                 # image captioning (port 7860)

# Course 3 — ChromaDB apps
cd Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search && python3 -m app.run_search
cd Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records && python similarity_employeedata.py
```

Notes:

- Free OpenRouter models rotate; if you hit "model not found," update `LLM_MODEL_ID` in config or use `openrouter/free`.
- The first run of the Icebreaker downloads the local embedding model (~80 MB); afterwards it works offline.
- The RAG lab notebook (`RAG_Lab.ipynb`) targets IBM watsonx.ai inside the Coursera/Skills Network environment — retained as a reference, does not run locally without IBM credentials.
- Course 3 projects use `all-MiniLM-L6-v2` embeddings downloaded automatically on first run.

---

## Progress / Future Work

**Completed**

- Course 1 — Develop Generative AI Applications: Get Started (3 projects)
- Course 2 — Build RAG Applications: Get Started (icebreaker bot, Gradio demos, Personal Branding Agent foundation)
- Course 3 — Vector Databases for RAG: An Introduction (3 ChromaDB search projects)

**In Progress**

- Personal Branding Agent — RAG pipeline (ingest → retrieve → generate → evaluate → publish) per `PLAN.md` (10 phases)

**Upcoming**

- Advanced RAG and vector retrieval (Course 4)
- Multimodal AI (Course 5)
- AI agents and tool calling (Course 6)
- LangGraph (Course 7)
- Multi-agent frameworks: CrewAI, AutoGen/AG2, BeeAI (Course 8)
- MCP / FastMCP (Course 9)
- RAG and Agentic AI Capstone (Course 10)
