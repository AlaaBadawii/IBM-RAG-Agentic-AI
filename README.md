# IBM RAG and Agentic AI Professional Certificate

This repository contains my hands-on work while completing IBM's **RAG and Agentic AI Professional Certificate** (Coursera). It is an engineering learning portfolio, not the official IBM course material — I work through each course's guided projects, then rebuild them from scratch and extend them, swapping the proprietary IBM watsonx.ai stack for free alternatives (OpenRouter + local Hugging Face models) so everything runs on a normal machine.

The goal is practical, working understanding of:

- LLM applications and prompt engineering
- LangChain (LCEL, chains, structured output)
- Retrieval-Augmented Generation (RAG)
- Embeddings and vector databases
- AI agents, agentic workflows, and multi-agent systems
- MCP and related agent infrastructure (upcoming courses)

Everything below that claims something was "implemented" is grounded in code that actually lives in `course-1/` and `course-2/`. Topics listed as *planned* are from the certificate's own syllabus and have **not** been implemented here yet.

---

## Progress

**Progress: 2 / 10 completed — Course 3 in progress**

```
[██████░░░░]  2 / 10 completed
```

| # | Course | Status |
|---|---|---|
| 1 | Develop Generative AI Applications: Get Started | **Completed** |
| 2 | Build RAG Applications: Get Started | **Completed** |
| 3 | Vector Databases for RAG: An Introduction | **In Progress** |
| 4 | Advanced RAG with Vector Databases and Retrievers | Not Started |
| 5 | Build Multimodal Generative AI Applications | Not Started |
| 6 | Fundamentals of Building AI Agents | Not Started |
| 7 | Agentic AI with LangChain and LangGraph | Not Started |
| 8 | Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI | Not Started |
| 9 | Build AI Agents using MCP | Not Started |
| 10 | RAG and Agentic AI Capstone Project | Not Started |

> Note: `course-3/` does not exist in this repository yet — the directory will be created when I begin the Course 3 labs. Courses 1 and 2 are fully completed; Courses 4–10 have not been started.

---

## Learning Roadmap

The certificate (and this repository) progresses in roughly this order. This is the **course roadmap** — only the first two stages have been completed in code so far:

```
LLM Applications
      ↓
Prompt Engineering / LangChain
      ↓
RAG                                    ← completed (Course 2)
      ↓
Embeddings / Vector Databases          ← in progress (Course 3)
      ↓
Advanced Retrieval
      ↓
Multimodal AI
      ↓
AI Agents / Tool Calling
      ↓
Agentic Workflows
      ↓
Multi-Agent Systems
      ↓
MCP
      ↓
Capstone
```

---

## Courses

### Course 1 — Develop Generative AI Applications: Get Started

**Status: Completed**

IBM's course focuses on the fundamentals of building generative AI applications: LLM APIs, prompt templates, few-shot prompting, LangChain chains (LCEL), and forcing models to produce structured output. The guided project is a Flask + LangChain app that returns structured JSON instead of free text.

**Repository work** — I rebuilt the guided project and then built two more applications in the same style, all using OpenRouter instead of watsonx.ai:

- **GenAI Flask App** (`course-1/GenAI_Flask_App/`) — the course guided project rebuilt: type a message, pick a model (Llama / Granite / Mistral), get back a validated JSON response (`summary`, `sentiment`, `response`). A single shared `ChatPromptTemplate` + `JsonOutputParser` pipe replaced the course's three per-model raw-text templates. Includes a Flask-free CLI sanity check (`llm_test.py`).
- **AI Email Assistant** (`course-1/AI_Email_Assistant/`) — generates polished emails (subject + body + improvement suggestions) as structured JSON. Adds a **Compare All** mode that runs the same prompt across four models in parallel and shows per-model latency, length, and a subject-quality score. Modular layout: `config` / `model` / `parser` / `prompts` / `services`. The detailed build log in `plan.md` documents real bugs I hit (wrong OpenRouter base URL causing DNS failures, intermittent `OutputParserException` on markdown-wrapped JSON, dependency drift between langchain versions).
- **Book/Movie Advisor** (`course-1/Book_Movie_Advisor/`) — takes a free-text mood and returns exactly 3 structured recommendation cards via a Pydantic `RecommendationList` schema. Selectable among a configurable set of OpenRouter models.

**Key things learned**

- LCEL pipe chains: `prompt | llm | parser` is a runnable, testable unit.
- Structured output: Pydantic schema + `JsonOutputParser` converts free-text model output into validated Python dicts; format instructions get injected into the prompt.
- Prompt engineering: reusable `PromptTemplate`s with input vs. partial variables, few-shot examples, and JSON-literal escaping (`{{ }}`).
- Why chat-completions APIs (OpenAI/OpenRouter) eliminate per-model special-token templates.
- Debugging order for LLM apps: key present → provider reachable → chain direct call → Flask → UI.

---

### Course 2 — Build RAG Applications: Get Started

**Status: Completed**

IBM's course introduces RAG: document loading, chunking/splitting, embeddings, vector stores, retrieval, similarity search, and query engines — taught through LlamaIndex and Gradio. The progression is from a plain LLM app toward a retrieval-augmented one.

**Repository work**

- **LinkedIn Icebreaker Bot** (`course-2/icebreaker/`) — a from-scratch rebuild of the course's LlamaIndex lab, with the provider swapped from watsonx to **OpenRouter (LLM) + local Hugging Face embeddings** (`all-MiniLM-L6-v2`, free and offline). A complete RAG pipeline built file-by-file:
  - `modules/data_extraction.py` — profile data loading (mock JSON or the discontinued ProxyCurl API).
  - `modules/data_processing.py` — `SentenceSplitter` chunking, `VectorStoreIndex` construction, and an embedding-integrity check.
  - `modules/query_engine.py` — generation via a LlamaIndex query engine, plus a **hand-written retrieval** path (`as_retriever()` → top-k nodes → context assembly) to expose every RAG stage explicitly.
  - `main.py` (CLI) and `app.py` (Gradio UI with runtime model switching and per-session indexes).
  - A ~1400-line `PLAN.md` walking through the build, and the pinned `requirements.txt` (`llama-index-core 0.14.x`).
- **RAG Lab** (`course-2/PersonalBrandingAgent/RAG_Lab.ipynb`) — the completed course notebook *"Summarize Private Documents Using RAG, LangChain, and LLMs"*: `TextLoader` → `CharacterTextSplitter` (chunk_size=1000) → `HuggingFaceEmbeddings` + Chroma → watsonx LLM → `RetrievalQA`, `ConversationBufferMemory`, `ConversationalRetrievalChain`, and a "wrap it into an agent" function. Includes source-return and model-swap exercises.
- **Personal Branding Agent** (`course-2/PersonalBrandingAgent/`) — a production-oriented extension of the course's RAG material (detailed below). This is where the RAG concepts are being applied to a real project.
- **Gradio demos** (`course-2/Gradio/`) — a `gr.Interface` sentence builder and a transformers/torchvision image-captioning demo, for Gradio UI practice.

**Key things learned**

- The RAG pipeline as a loop: load → split → embed → store → index → retrieve → generate.
- Chunking matters: `chunk_size`/`chunk_overlap` trade-offs and sentence-boundary splitting.
- Embeddings turn text into vectors so similarity search can be semantic, not keyword-based.
- LlamaIndex's `VectorStoreIndex`/`as_query_engine` hides retrieval; `as_retriever()` exposes it — good for learning what the abstraction is doing.
- Retrieval quality is upstream of generation quality: garbage in → grounded-but-wrong answers out.
- Provider-agnostic frameworks (LlamaIndex) mean swapping watsonx for OpenRouter only touches the factory files.

---

### Course 3 — Vector Databases for RAG: An Introduction

**Status: In Progress**

IBM's course teaches vector databases from the inside out: how embeddings become vector representations, vector collections, adding/updating/deleting documents, similarity search, and distance metrics — with hands-on ChromaDB labs.

**Completed so far**

No dedicated Course 3 work has been committed to this repository yet — the `course-3/` directory does not exist. The only vector-database experience present so far is incidental to Course 2:

- Chroma used in the completed RAG lab (`Chroma.from_documents`).
- LlamaIndex's in-memory `VectorStoreIndex` used in the Icebreaker Bot.
- A persistent Chroma store *planned* (not yet built) for the Personal Branding Agent.

**Still to learn in Course 3**

- ChromaDB collections and CRUD (add / update / delete documents)
- Vector representations and embeddings in depth
- Similarity search and distance metrics (cosine, Euclidean, dot product)
- Vector-database internals and how search scales
- Dedicated recommendation / search experiments
- RAG experiments built directly on a vector database

I will create `course-3/` when I start the labs.

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
| 10 | RAG and Agentic AI Capstone Project | A full end-to-end agentic RAG project |

None of these have been started. No projects for these courses exist in the repository.

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
- Retrieval chains: `RetrievalQA`, `ConversationalRetrievalChain`, `ConversationBufferMemory`
- Grounded prompting ("use only the information provided in the context")
- Manual retrieval with explicit top-k node assembly

### Vector Databases

- **Chroma** — used in the completed RAG lab; persistent Chroma *planned* for the Personal Branding Agent
- LlamaIndex in-memory vector store / `VectorStoreIndex`
- Embedding verification (checking every node got a non-null vector)
- Note: dedicated vector-database work is the subject of Course 3 (in progress)

### LinkedIn Integration (applied in the Personal Branding Agent)

- LinkedIn OAuth 2.0 flow (authorization code → tokens, refresh handling)
- Publishing posts via the LinkedIn REST API (`/rest/posts`, `userinfo`, `w_member_social` scope)

### Coming Later in the Certificate

Technologies from the certificate syllabus that are **not yet demonstrated** in this repository: FAISS, LangGraph, CrewAI, AutoGen/AG2, BeeAI, MCP/FastMCP, advanced retrieval/reranking, multimodal models, AI evaluation frameworks, and AI security.

---

## Projects and Experiments

The most technically meaningful work in the repository.

### GenAI Flask App — structured JSON output via LCEL

A Flask app where you type a message and receive a validated JSON object (`summary`, `sentiment` 0–100, `response`) from a selectable model. Rebuild of the IBM guided project, with watsonx swapped for OpenRouter.

**Concepts:** prompt templates, LCEL chains, structured output, provider abstraction.
**Technologies:** Flask, LangChain (`ChatPromptTemplate`, `JsonOutputParser`), Pydantic, OpenRouter (`ChatOpenAI` + `base_url`).
**What I learned:** the chain `prompt_template | model | json_parser` is the whole backend; format instructions injected into the prompt make free-text models conform to a schema. A shared chat template replaced three per-model token-wrapped templates once the provider exposed chat-completions.

### AI Email Assistant — multi-model generation + comparison

Generates complete emails (subject, body, tone, improvement suggestions) as structured JSON, with a **Compare All** mode that generates the same email with four models in parallel and renders per-model cards with time, length, and a subject-quality heuristic.

**Concepts:** few-shot prompting for JSON, model evaluation (latency/length/quality), parallel frontend fan-out, XSS-safe rendering.
**Technologies:** Flask, LangChain LCEL, Pydantic, OpenRouter, vanilla JS (`Promise.all`).
**What I learned:** evaluation can be a cheap heuristic stand-in before real judges; the backend stays simple when the frontend fans out per model; dict-key names in `MODELS` (internal) vs. values (provider slugs) is an easy source of confusion.

### Book/Movie Advisor — structured recommendation generation

Free-text mood → exactly 3 recommendation cards, validated by a nested Pydantic schema (`RecommendationList`), with a configurable model dropdown.

**Concepts:** nested structured output, `Literal` type constraints, few-shot format locking.
**Technologies:** Flask, LangChain, Pydantic, OpenRouter.
**What I learned:** constraining "exactly 3 items" is done in the prompt *and* the schema; `int` scores (mood_match 0–10) need explicit schema descriptions or models drift out of range.

### LinkedIn Icebreaker Bot — a RAG app built from scratch

A complete LlamaIndex RAG application rebuilt from the course lab: load a LinkedIn profile, chunk it, embed it with a local model, index it, and answer questions with grounded facts via an OpenRouter LLM. CLI and Gradio UIs.

**Concepts:** full RAG pipeline, sentence splitting, semantic retrieval, grounding, provider-agnostic design.
**Technologies:** LlamaIndex (core 0.14.x), `llama-index-llms-openrouter`, `llama-index-embeddings-huggingface`, `sentence-transformers`, Gradio.
**What I learned:** building each stage by hand (extract → split → embed → index → retrieve → generate) demystifies what query engines do under the hood; runtime model switching is just re-reading the model ID from config at call time; verifying embeddings catches silent indexing failures.

### Personal Branding Agent — RAG applied to a real project (in progress)

A production-oriented agent that generates, evaluates, and publishes authentic LinkedIn posts grounded in a personal knowledge base. Currently the **knowledge base** (a structured `data/` corpus: completed/in-progress projects, courses, certificates, evidence with evidence states, stories/lessons, vision, writing style, positioning) and the **LinkedIn OAuth integration** are done; the ingest → retrieve → generate → evaluate → publish pipeline is **planned but not yet built** (`PLAN.md` defines 10 phases).

**Concepts:** evidence-grounded generation, deterministic agent workflows with quality gates (PASS / REVISE / REJECT), metadata-aware retrieval, human-in-the-loop publishing, audit trails.
**Technologies:** LangChain + Chroma (planned), `sentence-transformers`, OpenRouter, Flask (planned), LinkedIn OAuth (`Auth_handling/`).
**What I learned so far:** RAG is a capability of an agent, not the agent itself; separating knowledge / reasoning / generation / evaluation / tools / observability keeps each evolvable; a working OAuth + publish path is the hard external-integration part, and it exists.

### Gradio experiments

A sentence-builder `gr.Interface` (sliders, dropdowns, checkboxes) and a transformers/torchvision image demo — hands-on practice with Gradio's component model.

**Concepts:** Gradio interfaces, image preprocessing (resize/crop/normalize), Hugging Face model inference.
**Technologies:** Gradio, transformers, torchvision.

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

This IBM repository is one part of a broader progression toward AI engineering. In parallel, I maintain a **separate repository focused on building AI agents from scratch** (`~/LLMs/AI-Agents/`), where I implement the underlying mechanics directly:

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
├── course-1/                                # COMPLETED
│   ├── GenAI_Flask_App/                     # Flask + LangChain structured JSON output
│   ├── AI_Email_Assistant/                  # multi-model email generator + Compare All
│   └── Book_Movie_Advisor/                  # mood → structured recommendations
├── course-2/                                # COMPLETED
│   ├── icebreaker/                          # LlamaIndex RAG app (CLI + Gradio)
│   └── PersonalBrandingAgent/               # RAG + LinkedIn OAuth agent (in progress)
│       ├── data/                            # structured personal knowledge base
│       ├── Auth_handling/                   # LinkedIn OAuth + publish scripts
│       ├── docs/                            # architecture / phases / evaluation / ADRs
│       ├── PLAN.md                          # 10-phase roadmap
│       └── RAG_Lab.ipynb                    # completed course RAG notebook
│   └── Gradio/                              # Gradio UI practice demos
├── course-3/                                # NOT CREATED YET (in progress)
├── .env.example                             # OPENROUTER_API_KEY=your_key_here
├── .gitignore                               # .env, venvs, __pycache__
└── README.md                                # this file
```

---

## Setup

Each project is self-contained with its own `requirements.txt` (or pinned environment) and uses environment variables for secrets. **Never commit `.env` files.**

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
| `course-1/GenAI_Flask_App/` | `OPENROUTER_API_KEY`, optional `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME` |
| `course-1/AI_Email_Assistant/` | `OPENROUTER_API_KEY` |
| `course-1/Book_Movie_Advisor/` | `OPENROUTER_API_KEY` |
| `course-2/icebreaker/` | `OPENROUTER_API_KEY`, optional `LLM_MODEL_ID`, `PROXYCURL_API_KEY` |
| `course-2/PersonalBrandingAgent/` | `OPENAI_API_KEY` (OpenRouter key, per its `config.py`), `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` |

> Example only: `OPENROUTER_API_KEY=your_key_here` — get a free key at <https://openrouter.ai/keys>.

### Running the apps

```bash
# Course 1 — Flask apps (default port 5000)
cd course-1/GenAI_Flask_App && python llm_test.py    # sanity check, no Flask
cd course-1/GenAI_Flask_App && python app.py         # or the other course-1 apps

# Course 2 — Icebreaker (LlamaIndex RAG)
cd course-2/icebreaker && python main.py --mock      # CLI with mock data
cd course-2/icebreaker && python app.py              # Gradio UI (port 5000)

# Course 2 — Gradio demos
cd course-2/Gradio && python app.py                  # sentence builder (port 7860)

# Course 2 — Personal Branding Agent
cd course-2/PersonalBrandingAgent && python Auth_handling/linkedin_oauth_setup.py   # one-time OAuth
```

Notes:

- The Icebreaker Bot's free OpenRouter models rotate; if you hit "model not found", update `LLM_MODEL_ID` in `config.py` or use `openrouter/free`.
- The first run of the Icebreaker downloads the local embedding model (~80 MB); afterwards it works offline.
- The RAG lab notebook (`RAG_Lab.ipynb`) targets IBM watsonx.ai inside the Coursera/Skills Network environment — it is retained as a reference and does not run locally without IBM credentials.

---

## Progress / Future Work

**Completed**

- Course 1 — Develop Generative AI Applications: Get Started
- Course 2 — Build RAG Applications: Get Started

**In Progress**

- Course 3 — Vector Databases for RAG: An Introduction (`course-3/` to be created)
- Personal Branding Agent (RAG pipeline to be built per `PLAN.md`)

**Upcoming**

- Advanced RAG and vector retrieval (Course 4)
- Multimodal AI (Course 5)
- AI agents and tool calling (Course 6)
- LangGraph (Course 7)
- Multi-agent frameworks: CrewAI, AutoGen/AG2, BeeAI (Course 8)
- MCP / FastMCP (Course 9)
- RAG and Agentic AI Capstone (Course 10)