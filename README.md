# IBM RAG and Agentic AI Professional Certificate

> Hands-on engineering portfolio built alongside the IBM specialization: course labs rebuilt from scratch plus independent extensions — RAG pipelines, vector search, multimodal apps, and tool-calling agents, running on free-tier providers (OpenRouter, local Hugging Face models, Gemini) instead of the proprietary watsonx.ai stack.

---

## About the Program

**IBM RAG and Agentic AI Professional Certificate** — a 10-course specialization on Coursera by IBM Skills Network.

> Build real-world AI with RAG and agentic AI. Use AI tools to streamline automation, drive innovation & take your career further, faster.

**Instructors:** IBM Skills Network Team (Wojciech 'Victor' Fulmyk, Ricky Shi)

**Program stats:** 10-course series · 4.6 rating (1,126 reviews) · 105,310+ enrolled · Advanced level · Flexible schedule (8 weeks at 3 hours/week)

---

## Repository at a Glance

| # | Course | Status | Projects in this repo |
|---|---|---|---|
| 1 | Develop Generative AI Applications: Get Started | **Completed** | GenAI Flask App · AI Email Assistant · Book/Movie Advisor |
| 2 | Build RAG Applications: Get Started | **In Progress** (substantial) | LinkedIn Icebreaker Bot · Personal Branding Agent · Gradio demos |
| 3 | Vector Databases for RAG: An Introduction | **Completed** | Books Advanced Search · Food Recommendation System · Employee Similarity Search (+ Job Matcher plan) |
| 4 | Advanced RAG with Vector Databases and Retrievers | **In Progress** | YouTube RAG Summarizer & QA (working baseline, rebuild planned) |
| 5 | Build Multimodal Generative AI Applications | **In Progress** (substantial) | Image Captioning · Vocab Learning App · Personal Storyteller · Style Finder · Nutrition Coach (+ 1 stub) |
| 6 | Fundamentals of Building AI Agents | **In Progress** (substantial) | AI Math Assistant · AI-Powered Data Analysis with LCEL |
| 7 | Agentic AI with LangChain and LangGraph | Not Started | — |
| 8 | Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI | Not Started | — |
| 9 | Build AI Agents using MCP | Not Started | — |
| 10 | RAG and Agentic AI Capstone Project | Not Started | — |

19 tracked items: 17 working implementations (including the YouTube single-file baseline), 1 plan-only (Job Matcher), 1 stub (Meeting Assistant).

---

## Courses and Projects

### Course 1 — Develop Generative AI Applications: Get Started

**Status: Completed.** IBM's course covers LLM APIs, prompt templates, few-shot prompting, LangChain chains (LCEL), and structured output. The guided project is a Flask + LangChain app returning structured JSON. I rebuilt it and added two more apps in the same style, all on OpenRouter instead of watsonx.ai.

See [`Develop_Generative_AI_Applications_Get_Started/README.md`](Develop_Generative_AI_Applications_Get_Started/README.md).

#### GenAI Flask App

Type a message, pick a model (Llama / Granite / Mistral), get back validated JSON (`summary`, `sentiment`, `response`). A single shared `ChatPromptTemplate` + `JsonOutputParser` pipe replaced the course's three per-model raw-text templates. Includes a Flask-free CLI sanity check (`llm_test.py`).

**Status:** Completed · **Technologies:** Flask, LangChain LCEL, Pydantic, OpenRouter · **Engineering focus:** prompt templates, structured output, provider abstraction.

#### AI Email Assistant

Generates polished emails (subject + body + improvement suggestions) as structured JSON. Adds a **Compare All** mode that runs the same prompt across four models in parallel and shows per-model latency, length, and a subject-quality score. The build log in `plan.md` documents real bugs (wrong OpenRouter base URL causing DNS failures, intermittent `OutputParserException` on markdown-wrapped JSON, langchain version drift).

**Status:** Completed · **Technologies:** Flask, LangChain LCEL, Pydantic, OpenRouter, vanilla JS (`Promise.all`) · **Engineering focus:** parallel fan-out, model comparison, XSS-safe rendering.

#### Book/Movie Advisor

Free-text mood → exactly 3 recommendation cards validated by a nested Pydantic schema (`RecommendationList`), with a configurable OpenRouter model dropdown.

**Status:** Completed · **Technologies:** Flask, LangChain, Pydantic, OpenRouter · **Engineering focus:** nested structured output, `Literal` constraints, few-shot format locking.

**Key things learned (Course 1)**

- LCEL pipe chains: `prompt | llm | parser` is a runnable, testable unit.
- Structured output: Pydantic schema + `JsonOutputParser` turns free text into validated dicts.
- Prompt engineering: input vs. partial variables, few-shot examples, JSON-literal escaping (`{{ }}`).
- Debugging order: key present → provider reachable → chain direct call → Flask → UI.

---

### Course 2 — Build RAG Applications: Get Started

**Status: In Progress (substantial).** IBM's course introduces RAG — document loading, chunking, embeddings, vector stores, retrieval, similarity search, query engines — taught through LlamaIndex and Gradio.

See [`Build_RAG_Applications_Get_Started/README.md`](Build_RAG_Applications_Get_Started/README.md).

#### LinkedIn Icebreaker Bot

From-scratch rebuild of the course's LlamaIndex lab, provider swapped from watsonx to **OpenRouter (LLM) + local Hugging Face embeddings** (`sentence-transformers/all-MiniLM-L6-v2`, free and offline). Full pipeline: profile loading (mock JSON; ProxyCurl API since discontinued) → `SentenceSplitter` chunking → `VectorStoreIndex` → query engine plus a hand-written retrieval path (`as_retriever()` → top-k → context assembly). CLI (`main.py --mock`) and Gradio UI with runtime model switching.

**Status:** Completed lab rebuild · **Technologies:** LlamaIndex (core 0.14.x), `llama-index-llms-openrouter`, `llama-index-embeddings-huggingface`, Gradio · **Engineering focus:** full RAG pipeline, grounding, provider-agnostic design.

#### Personal Branding Agent

The flagship project of this repository: a production-oriented agent that generates, verifies, and publishes authentic LinkedIn posts grounded in a curated personal knowledge base. Substantially implemented — ~110 source files across 14 packages, ~55 test files, 10 ADRs, full operations docs.

- **Knowledge base:** structured `data/` corpus (projects, courses, certificates, evidence with state tracking, stories/lessons, vision, writing style, positioning) + registered sources (`sources.yaml`) with incremental sync into persistent Chroma.
- **Retrieval:** `RetrievalEngine` facade with 6 strategies — vector, metadata, BM25, multi-query, RRF-hybrid fusion, cross-encoder reranking — plus metadata/strata scoping and a 12-query gold set with evaluation docs.
- **Generation + verification:** evidence-cited generation on a pinned Gemini model (native SDK), decline-before-call on insufficient evidence, deterministic verification gates (claim splitting, number/date matching, forbidden-inference rules) with an advisory LLM judge consulted only after deterministic checks pass.
- **Publishing:** duplicate-safe publish path (exact hash, embedding near-duplicate, topic overuse), write-ahead intents in SQLite, LinkedIn write API via an injectable-transport client; read/interaction APIs explicitly out of scope.
- **Operations:** SQLite state store (WAL, forward-only migrations) for runs, intents, publications, locks; two cron-triggered workflows (sync daily, branding every 8h) with PID-liveness-gated locking; deterministic SMTP notifications; autonomous-evaluation suite covering ambiguous-publish and failure scenarios.
- **Caveats (per the project's own docs):** no real sources synchronized yet through the new sync entry point, and the `unknown_requires_review` state has no operator resolution API — publishing halts safely until it is built.

**Status:** Substantially implemented, production-oriented (not yet live-operated) · **Technologies:** Chroma, `sentence-transformers`, Gemini (native SDK), OpenRouter (multi-query path), SQLite, SMTP, LinkedIn REST API · **Engineering focus:** hybrid retrieval + reranking, evidence grounding, deterministic quality gates, idempotent publishing, workflow scheduling, evaluation.

#### Gradio Demos

A `gr.Interface` sentence builder and a BLIP image-captioning demo — Gradio component practice supporting the icebreaker UI.

**Status:** Completed lab demos · **Technologies:** Gradio, transformers, torch · **Engineering focus:** UI component model, image preprocessing.

**Key things learned (Course 2)**

- The RAG loop: load → split → embed → store → index → retrieve → generate.
- Chunking (`chunk_size`/`chunk_overlap`, sentence boundaries) is a design decision, not a default.
- `VectorStoreIndex`/`as_query_engine` hides retrieval; `as_retriever()` exposes it.
- Retrieval quality bounds generation quality; providers swap at factory files only.

---

### Course 3 — Vector Databases for RAG: An Introduction

**Status: Completed.** IBM's course teaches vector databases from the inside: embeddings, collections, CRUD, similarity search, distance metrics — with ChromaDB labs.

See [`Vector_Databases_for_RAG_An_Introduction/README.md`](Vector_Databases_for_RAG_An_Introduction/README.md).

#### Books Advanced Search

Modular app (data → documents → vector_store → repository → search) storing 8 book records in persistent ChromaDB. Four exercises: similarity search, genre filtering (`$in`), rating filtering (`$gte`), combined semantic + metadata search, with idempotent upserts and pytest coverage.

**Status:** Completed · **Technologies:** ChromaDB (`PersistentClient`), `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim, cosine) · **Engineering focus:** layered architecture, metadata `where` clauses, tested search.

#### Food Recommendation System

Three-tier progression over the committed food dataset (`data/FoodDataSet.json`): interactive semantic search → advanced search with cuisine/calorie filters → conversational RAG chatbot, plus independent extensions (calorie checker, result limiter, system comparison).

**Status:** Completed · **Technologies:** ChromaDB, `sentence-transformers`, NumPy, OpenRouter-compatible LLM (chatbot tier only) · **Engineering focus:** progressive retrieval complexity, filter design, RAG chat.

#### Similarity Search on Employee Records

Single-file in-memory ChromaDB demo: 2 pure similarity searches, 3 metadata filters (department, experience, location), 1 combined query.

**Status:** Completed lab demo · **Technologies:** ChromaDB, `sentence-transformers` · **Engineering focus:** `query()`/`get()`, cosine distance, metadata operators.

#### Job Description Matcher

Semantic job search over ~30 descriptions with evaluation metrics (Hit@K, Precision@K) and an optional LCEL summary step.

**Status:** Plan only (`plan.md`, `README.md`, `requirements.txt`; implementation not yet built) · **Technologies (planned):** ChromaDB, `sentence-transformers`.

**Key concepts practiced (Course 3)**

- ChromaDB collections: create, ingest, query, persist.
- Metadata filtering: `$in`, `$gte`, `$lte`, `$and`, `$or` inside `collection.query()`.
- Document construction: combining fields into effective searchable text.

---

### Course 4 — Advanced RAG with Vector Databases and Retrievers

**Status: In Progress.** Work has started ahead of the certificate order via a single-project deep dive.

#### YouTube RAG Summarizer & QA

YouTube URL → transcript fetch → dual path: direct map-reduce summarization plus chunk → embed → FAISS → retrieve → grounded Q&A, served in a Gradio `Blocks` UI. The current `ytbot.py` (~650 lines) is a working single-file baseline on the IBM watsonx stack (`granite-4-h-small`, `granite-embedding-278m-multilingual`); `PLAN.md` defines a provider-independent layered rebuild (OpenRouter seams, timestamp-preserving chunks, evaluation) that is not yet built.

**Status:** Working baseline, rebuild planned · **Technologies:** Gradio, LangChain (`RecursiveCharacterTextSplitter`, `PromptTemplate`), FAISS (`langchain-community`), `langchain-ibm`, `youtube-transcript-api` · **Engineering focus:** transcript handling, map-reduce summarization, vector Q&A over captions.

---

### Course 5 — Build Multimodal Generative AI Applications

**Status: In Progress (substantial).** Five of six labs are working implementations; one remains a stub (lab instructions only, no code).

#### Image Captioning

CLI + FastAPI + Gradio image→text service (caption, VQA, counting, extraction) with provider abstraction over OpenRouter vision models, retry/fallback, ADR-documented decisions, a JSON evaluation harness, Docker packaging (`Dockerfile`, `docker-compose.yml`), and 7 unit + 1 integration test files.

**Status:** Completed · **Technologies:** FastAPI, Uvicorn, Gradio, OpenAI SDK pointed at OpenRouter, Pillow, Docker · **Engineering focus:** provider abstraction, resilience (retry/fallback), evaluation harness, containerized serving.

#### Vocab Learning App

Vocabulary list → validated JSON definitions/examples/story (bounded retries) → single MP3 audio lesson in a Gradio UI, with 5 pytest files covering vocabulary, LLM, validation, audio, and pipeline.

**Status:** Completed · **Technologies:** Gradio, OpenRouter-compatible chat API via `requests`, gTTS · **Engineering focus:** validated generation loops, TTS lesson assembly, tested pipeline.

#### Personal Storyteller

Topic-in → LLM educational story + MP3 narration via a minimal single-file Gradio app (OpenRouter-compatible endpoint, `meta-llama` default).

**Status:** Completed (minimal) · **Technologies:** Gradio, OpenRouter-compatible API, gTTS · **Engineering focus:** story generation + narration loop.

#### Style Finder

Fashion-photo analyzer: matches uploads against precomputed outfit embeddings (ResNet50 + cosine similarity), then generates retail-style analysis with item/price/link via a Llama-4 vision model. Runs on the IBM watsonx stack.

**Status:** Completed lab · **Technologies:** Gradio, torch/torchvision (ResNet50), scikit-learn, `ibm-watsonx-ai`, pandas · **Engineering focus:** embedding-based visual matching, vision-LLM analysis.

#### AI Nutrition Coach (`cal_coach_app`)

Flask food-photo coach: base64-encodes uploads for a Llama-4 vision model and renders calorie/nutrient/health reports as HTML.

**Status:** Completed lab · **Technologies:** Flask, `ibm-watsonx-ai`, Pillow · **Engineering focus:** vision prompting for structured nutrition output, web rendering.

#### AI Meeting Assistant

Intended meeting transcription/summarization app (Whisper + Gradio + watsonx per the lab instructions).

**Status:** Stub — lab instructions only, no implementation.

---

### Course 6 — Fundamentals of Building AI Agents

**Status: In Progress (substantial).** Two working tool-calling-agent projects; the old "Not Started" label predates them.

#### AI Math Assistant

LangChain agent that performs arithmetic via 7 tools (`add`, `add_with_options`, `sum_complex`, `sum_from_text`, `subtract`, `multiply`, `divide`) plus Wikipedia lookup (patched `User-Agent`, mocked in tests). Agent built with `langchain.agents.create_agent` (LangGraph-backed) on an OpenRouter model (`deepseek` flash default). 8 pytest files; project README reports 37 tests, offline-safe.

**Status:** Completed · **Technologies:** LangChain 1.x, LangGraph, `langchain-openai` (OpenRouter base URL), `langchain-community` (Wikipedia), pytest · **Engineering focus:** `@tool` design, agent loop, mocked external calls.

#### AI-Powered Data Analysis with LCEL

Conversational CSV agent: inspects local datasets and reports classification-vs-regression with evidence (sample rows, `describe` stats, trained baseline scores). 6 tools: file listing, dataset preload/cache, schema summaries, `head`/`tail`/`describe` dispatch, `RandomForestClassifier` accuracy probe, `RandomForestRegressor` R²/MSE probe. Ships with Breast Cancer Wisconsin (project reports ~95% accuracy) and California Housing (project reports R² ~0.82) datasets. Built as a classic OpenAI-tools agent (`create_openai_tools_agent` + `AgentExecutor`, 15 max iterations) on OpenRouter; 9 offline pytest tests.

**Status:** Completed · **Technologies:** LangChain 0.3.x, `langchain-openai` (OpenRouter), pandas, scikit-learn · **Engineering focus:** data-agent tool design, evidence-backed classification, error-shaped tool returns.

> Note: despite the directory name, the data-analysis agent uses the tools-agent pattern, not an LCEL `prompt | llm | parser` pipe.

---

### Courses 7–10 (Not Started)

| # | Course | Focus |
|---|---|---|
| 7 | Agentic AI with LangChain and LangGraph | Workflow graphs, state, tool use in LangGraph |
| 8 | Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI | Multi-agent frameworks and orchestration |
| 9 | Build AI Agents using MCP | Model Context Protocol, FastMCP, tool servers |
| 10 | RAG and Agentic AI Capstone Project | Full end-to-end agentic RAG project |

No projects for these courses exist in the repository yet.

---

## Technical Skills Demonstrated

Only technologies with real code in the repository are listed as demonstrated.

### LLM Application Development

- Python 3.10+
- LLM APIs via **OpenRouter** (OpenAI-compatible chat-completions), with runtime model switching; **Gemini** via native SDK (pinned model) in the Personal Branding Agent; **IBM watsonx.ai** in the YouTube baseline, Style Finder, and Nutrition Coach labs
- Prompt engineering: `PromptTemplate`/`ChatPromptTemplate`, few-shot examples, system prompts, partial vs. input variables
- Structured outputs: Pydantic schemas + LangChain `JsonOutputParser`
- LangChain chains and agents: **LCEL** (`prompt | llm | parser`), `create_openai_tools_agent` + `AgentExecutor`, `langchain.agents.create_agent` (LangGraph-backed)
- Flask web apps (routes, JSON APIs, template rendering) and FastAPI services
- Multi-model experimentation and side-by-side comparison (latency, length, quality scoring)
- Vanilla JS/CSS frontends with `fetch` and XSS-safe rendering

### RAG

- Full pipeline: load → split → embed → store → retrieve → generate
- Chunking: `CharacterTextSplitter`, `RecursiveCharacterTextSplitter`, LlamaIndex `SentenceSplitter`, deterministic content-hash chunk IDs
- Embeddings: local Hugging Face `sentence-transformers` (`all-MiniLM-L6-v2`); watsonx `granite-embedding-278m-multilingual` in IBM-stack labs
- LlamaIndex: `VectorStoreIndex`, `SentenceSplitter`, query engines, explicit retrievers
- Retrieval chains: `RetrievalQA`, `ConversationBufferMemory`, `ConversationalRetrievalChain`
- Advanced retrieval (Personal Branding Agent): BM25, RRF hybrid fusion, cross-encoder reranking, multi-query, metadata/strata scoping, gold-query evaluation
- Grounded prompting ("use only the information provided in the context"), evidence citations, decline-on-insufficient-evidence

### Vector Databases

- **ChromaDB** — collections, CRUD/upsert, persistence (`PersistentClient`), `query()` with `where` filters
- **FAISS** — vector Q&A over YouTube transcripts (`langchain-community`)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dim embeddings, cosine distance
- Metadata filtering: `$in`, `$gte`, `$lte`, `$and`, `$or`; combined semantic + metadata search

### Multimodal

- Vision-language models via OpenRouter (captioning, VQA, counting, extraction) and watsonx Llama-4 vision (style analysis, nutrition coaching)
- Image handling: base64 encoding, Pillow loading, torchvision preprocessing, ResNet50 embedding similarity
- Speech: gTTS narration (Storyteller, Vocab app); Whisper specified for the Meeting Assistant stub
- Serving: Gradio `Interface`/`Blocks` UIs, FastAPI + Uvicorn, Docker + Compose

### Agents & Automation

- `@tool`-based tool calling, OpenAI-style function-calling agents, bounded agent loops with max iterations
- Verification-first agent design: deterministic gates authoritative, LLM judge advisory-only
- Idempotent publishing (hash + embedding + overuse checks), SQLite-backed workflow state, cron scheduling with locking, SMTP failure notifications
- LinkedIn integration: OAuth 2.0 authorization-code flow with refresh handling, write-API publishing (`w_member_social`), structured error classification

### Testing & Evaluation

- pytest suites across Books (3 files), Image Captioning (7 unit + 1 integration), Vocab (5 files), Math Assistant (8 files), Data Analysis (9 tests), and ~55 files in the Personal Branding Agent (project reports ~979 passed)
- Retrieval evaluation: gold-query sets, Hit@K / Precision@K plans, RRF/rerank comparisons
- Deterministic autonomous-evaluation scenarios (ambiguous publish, failure, recovery paths)
- File-based evaluation harnesses (JSON cases) for vision output

### Coming Later in the Certificate

Not yet demonstrated with meaningful implementation: LangGraph workflow graphs (beyond the agent-helper default), CrewAI, AutoGen/AG2, BeeAI, MCP/FastMCP, and AI security topics.

---

## Engineering Concepts & Lessons

- **LLM apps are probabilistic + deterministic.** `prompt → model → parser → validated dict`: one uncontrolled call between deterministic glue (validation, parsing, HTTP). Parse and validate everything; treat model output as untrusted.
- **Why RAG is needed.** Models know nothing about your data unless it enters the prompt. RAG is the discipline of retrieving the right context so answers are grounded and current.
- **Embeddings capture meaning.** Similar sentences → similar vectors; chunk quality directly affects retrieval quality.
- **Retrieval quality limits generation quality.** A strong retriever with a weak generator beats the reverse — hence hybrid + rerank + evaluation.
- **Frameworks wrap a small set of ideas.** LlamaIndex's query engine is "embed → top-k → context → LLM"; LCEL is `prompt | model | parser`. Knowing the steps makes provider swaps (watsonx → OpenRouter touched only factories) and framework choices easy.
- **Deterministic gates beat vibe checks.** Claim splitting, exact-match number/date checks, and forbidden-inference rules catch what LLM judges wave through; keep the judge advisory.
- **Idempotency is a publishing requirement.** Content-hash intents, exact + near-duplicate + overuse checks, and SQLite-as-truth prevent double posts the way migrations prevent double applies.
- **Debugging order matters.** Key → network → chain directly → Flask → UI isolates failures fast.

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
│   ├── AI_Email_Assistant/                          # multi-model email generator + Compare All (+ plan.md)
│   └── Book_Movie_Advisor/                          # mood → structured recommendations
├── Build_RAG_Applications_Get_Started/                # Course 2 — IN PROGRESS
│   ├── icebreaker/                                  # LlamaIndex RAG app, CLI + Gradio (submodule)
│   ├── PersonalBrandingAgent/                       # RAG + LinkedIn agent (substantially implemented)
│   │   ├── app/                                     # 14 packages: agent, retrieval, generation, ...
│   │   ├── data/                                    # curated personal knowledge corpus
│   │   ├── Auth_handling/                           # LinkedIn OAuth + manual publish scripts
│   │   ├── docs/                                    # architecture / phases / evaluation / ADRs
│   │   ├── tests/                                   # ~55 test files
│   │   ├── ops/                                     # cron schedules
│   │   └── RAG_Lab.ipynb                            # course RAG notebook (reference)
│   └── Gradio/                                      # Gradio UI practice demos
├── Vector_Databases_for_RAG_An_Introduction/          # Course 3 — COMPLETED
│   ├── Books_Advanced_Search/                       # ChromaDB book search + tests
│   ├── Food_Recommendation_System/                   # food search → RAG chatbot (+ PLAN.md)
│   ├── Similarity_Search_on_Employee_Records/        # ChromaDB fundamentals demo
│   └── job_description_matcher/                      # plan + README (implementation pending)
├── Advanced_RAG_with_Vector_Databases_and_Retrievers/ # Course 4 — IN PROGRESS
│   └── youtube-rag-summarizer/                       # transcript summarize + FAISS Q&A (+ PLAN.md)
├── Build_Multimodal_Generative_AI_Applications/      # Course 5 — IN PROGRESS
│   ├── Image_Captioning/                             # FastAPI + Gradio vision service (+ Docker, tests)
│   ├── Vocab_Learning_App/                           # vocab → JSON lesson → MP3 (+ tests)
│   ├── Personal_Storyteller/                         # story + narration mini-app
│   ├── Style_Finder/                                 # outfit embedding match + Llama-4 analysis
│   ├── cal_coach_app/                                # Flask nutrition coach (Flask + watsonx vision)
│   └── AI_Meeting_Assistant/                         # stub: lab instructions only
├── Fundamentals_of_Building_AI_Agents/               # Course 6 — IN PROGRESS
│   ├── AI_Math_Assistant/                            # tool-calling math + Wikipedia agent (+ tests)
│   └── AI_Powered_Data_Analysis_with_LCEL/            # CSV classification/regression agent (+ tests, data)
├── .env.example                                     # OPENROUTER_API_KEY placeholder (root convention)
├── .gitignore                                       # .env, venvs, __pycache__, local chroma/state snapshots
└── README.md                                        # this file
```

Course-level overviews: [Course 1](Develop_Generative_AI_Applications_Get_Started/README.md) · [Course 2](Build_RAG_Applications_Get_Started/README.md) · [Course 3](Vector_Databases_for_RAG_An_Introduction/README.md)

---

## Setup

Each project is self-contained with its own dependencies and uses environment variables for secrets. **Never commit `.env` files** — root and project `.gitignore` files exclude `.env`, virtualenvs, caches, and local Chroma/SQLite snapshots.

1. Create and activate a virtual environment in the project directory:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies (per-project file):

```bash
pip install -r requirements.txt        # most projects
pip install -e .                       # only if a pyproject.toml project needs it (Image_Captioning)
```

3. Create your local `.env` from the project's `.env.example` and fill in keys:

```bash
cp .env.example .env
```

### Environment variables used by the projects

Variable **names** only — placeholders, never real values.

| Project | Variables |
|---|---|
| `Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App/` | `OPENROUTER_API_KEY`, optional `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME` |
| `Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant/` | `OPENROUTER_API_KEY` |
| `Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor/` | `OPENROUTER_API_KEY` |
| `Build_RAG_Applications_Get_Started/icebreaker/` | `OPENROUTER_API_KEY`, optional `LLM_MODEL_ID`, `PROXYCURL_API_KEY` (legacy/discontinued) |
| `Build_RAG_Applications_Get_Started/PersonalBrandingAgent/` | `GOOGLE_API_KEY` (pinned Gemini model, native SDK), `OPENROUTER_API_KEY` (multi-query path), `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `SMTP_*` (`HOST`, `PORT`, `SENDER`, `RECIPIENT`, `USERNAME`, `PASSWORD`, `TLS`) |
| `Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search/` | None required |
| `Vector_Databases_for_RAG_An_Introduction/Food_Recommendation_System/` | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (chatbot tier only) |
| `Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records/` | None required |
| `Vector_Databases_for_RAG_An_Introduction/job_description_matcher/` | None yet (planned) |
| `Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer/` | None (watsonx Skills Network auth in baseline; `OPENROUTER_API_KEY` planned for rebuild) |
| `Build_Multimodal_Generative_AI_Applications/Image_Captioning/` | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `OPENROUTER_FALLBACK_MODEL` |
| `Build_Multimodal_Generative_AI_Applications/Vocab_Learning_App/` | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` |
| `Build_Multimodal_Generative_AI_Applications/Personal_Storyteller/` | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (no committed `.env.example`; same convention as Vocab app) |
| `Build_Multimodal_Generative_AI_Applications/Style_Finder/` | IBM watsonx credentials via app config (no `.env.example`) |
| `Build_Multimodal_Generative_AI_Applications/cal_coach_app/` | IBM watsonx credentials via app config (no `.env.example`) |
| `Fundamentals_of_Building_AI_Agents/AI_Math_Assistant/` | `OPENROUTER_API_KEY`, `BASE_URL` |
| `Fundamentals_of_Building_AI_Agents/AI_Powered_Data_Analysis_with_LCEL/` | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` |

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

# Course 5 — Multimodal (representative)
cd Build_Multimodal_Generative_AI_Applications/Image_Captioning && python -m src.main     # CLI
cd Build_Multimodal_Generative_AI_Applications/Image_Captioning && uvicorn src.api.app:app --port 8000  # API
cd Build_Multimodal_Generative_AI_Applications/Vocab_Learning_App && python app.py         # Gradio vocab tutor

# Course 6 — Agents
cd Fundamentals_of_Building_AI_Agents/AI_Math_Assistant && pytest tests/                   # offline-safe suite
cd Fundamentals_of_Building_AI_Agents/AI_Powered_Data_Analysis_with_LCEL && pytest tests/ # offline tool tests
```

Notes:

- Free OpenRouter models rotate; if you hit "model not found," update the model id in config or use an `openrouter/free` fallback.
- First runs download local embedding models (~80 MB); afterwards local paths work offline.
- The RAG lab notebook (`RAG_Lab.ipynb`) and watsonx-based labs target IBM credentials/Skills Network environments — retained as references; OpenRouter-based rebuilds run locally.
- Course 3–4 local search projects download `all-MiniLM-L6-v2` automatically on first run.

---

## Progress / Next Steps

**Completed**

- Course 1 — Develop Generative AI Applications: Get Started (3 projects)
- Course 3 — Vector Databases for RAG: An Introduction (Books, Food, Employee; Job Matcher planned)
- Course 6 agents (first two): AI Math Assistant, AI-Powered Data Analysis
- Multimodal applications (Course 5): Image Captioning, Vocab Learning App, Personal Storyteller, Style Finder, Nutrition Coach

**In Progress**

- Personal Branding Agent — remaining: first real-source sync, first live post through the new service, operator resolution for `unknown_requires_review`, mention-triggered responses
- YouTube RAG Summarizer — provider-independent layered rebuild per `PLAN.md`
- Job Description Matcher — implementation from `plan.md`
- AI Meeting Assistant — implementation from lab instructions

**Upcoming**

- LangGraph workflows and state (Course 7)
- Multi-agent frameworks: CrewAI, AutoGen/AG2, BeeAI (Course 8)
- MCP / FastMCP tool servers (Course 9)
- RAG and Agentic AI Capstone (Course 10)
