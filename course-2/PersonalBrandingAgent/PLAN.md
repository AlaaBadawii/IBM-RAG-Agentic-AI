# Personal Branding Agent — Master Roadmap

## Project Goal

Build an **autonomous Personal Branding Agent**: a system whose decisions and
generated content are grounded in a RAG system built from a personal knowledge
base (`data/`), that can generate, evaluate, revise, and safely publish
authentic content to LinkedIn through an authenticated tool, while keeping an
auditable record of every decision and action.

This is the successor to the original **Course 2 RAG application** plan. The
older plan treated the project as "ingest Markdown → embed → retrieve →
generate → show in Flask → publish manually." The current project is now a
production-oriented, evidence-grounded Agent. RAG is a capability of the Agent,
not the Agent itself.

## Architecture Summary

The system separates concerns explicitly:

```text
Knowledge          RAG over the personal knowledge base (data/ → ChromaDB)
Reasoning          Agent workflow: goal → retrieve → generate → evaluate → revise → publish
Generation         LCEL chain producing candidate posts from structured context
Evaluation         Deterministic + LLM checks with quality gates (PASS / REVISE / REJECT)
Tools              LinkedIn publish tool, retrieval tool, future tools
Execution          CLI, Flask API, and (later) a scheduler — all talk to the Agent Core
Observability      Publication/decision history, evaluation logs, audit trail
```

Conceptually:

```text
                         ┌────────────────────────┐
                         │ Personal Branding Agent│
                         └───────────┬────────────┘
                                     │
          ┌──────────────────────────┼─────────────────────────┐
          │                          │                         │
          ▼                          ▼                         ▼
    Knowledge / RAG             Agent Reasoning           Tools
          │                          │                         │
          │                          │                         ├── LinkedIn
          │                          │                         ├── Retrieval
          │                          │                         └── Future tools
          ▼                          ▼
      ChromaDB                  Planning / Decisions
```

Detailed documents: `docs/architecture/system-overview.md`,
`docs/architecture/agent-architecture.md`, `docs/architecture/rag-architecture.md`,
`docs/architecture/linkedin-integration.md`, `docs/architecture/data-flow.md`.

## Current Implementation State

This status is based on an inspection of the repository, **not** on the old
plan. Components are marked `NOT STARTED` unless actually present.

| Area | Status | Evidence |
|---|---|---|
| Structured knowledge base (`data/`) | **DONE** | All categories present: completed/in-progress projects & courses, certificates, evidence (with evidence states), stories/lessons, vision, writing style, public positioning, audits |
| Configuration (`config.py`) | **DONE (basic)** | Env loading, model ID, gen params, embedding model, Chroma dir, chunk params |
| Dependency management (`requirements.txt`) | **DONE (basic)** | Flask, langchain*, chromadb, sentence-transformers, pydantic, python-dotenv, requests |
| Secrets / `.gitignore` | **DONE (basic)** | `.env`, `Auth_handling/linkedin_tokens.json`, `chroma_db/`, `__pycache__/`, `*.pyc` ignored |
| LinkedIn OAuth (`Auth_handling/`) | **DONE (working)** | `linkedin_oauth_setup.py`, `test_post.py`, `test_credentials.py`, saved tokens |
| Ingestion pipeline | **NOT STARTED** | No `ingest.py` / no `chroma_db/` |
| Retrieval engine | **NOT STARTED** | No `retriever.py` |
| Branding context engine | **NOT STARTED** | Raw material exists in `data/` (writing_style, vision_goals, public_positioning) |
| Generation | **NOT STARTED** | No `generator.py` / no `prompts/` |
| Evaluation | **NOT STARTED** | No evaluation module |
| Agent core / workflow | **NOT STARTED** | No `app/` package |
| LinkedIn tool integration layer | **NOT STARTED** | OAuth scripts exist; no clean tool interface |
| Autonomous execution | **NOT STARTED** | No scheduler / trigger |
| Observability / memory | **NOT STARTED** | No history store |
| Web app / API | **NOT STARTED** | No `app.py`, no `templates/` |
| Tests | **NOT STARTED** | No `tests/` |
| Documentation (`docs/`) | **DONE** | This roadmap + phase/architecture/evaluation/operations docs |

> `RAG_Lab.ipynb` is a historical course lab and is retained as a reference; it
> is not part of the production pipeline.

## Phase Roadmap

Each phase has a detailed document under `docs/phases/`. Phases are ordered by
dependency; a phase is complete only when its acceptance criteria pass.

| # | Phase | Purpose | Status |
|---|---|---|---|
| 1 | Foundation | Package structure, config, logging, errors, secrets, testing base | **PENDING** |
| 2 | Knowledge Ingestion | `data/` → clean, chunked, metadata-tagged, embedded → ChromaDB | **PENDING** |
| 3 | Retrieval Engine | Semantic + metadata-aware retrieval, filters, retrieval evaluation | **PENDING** |
| 4 | Branding Context Engine | Evidence + positioning + voice assembled into structured LLM context | **PENDING** |
| 5 | Content Generation | LCEL chain producing candidate LinkedIn posts from structured context | **PENDING** |
| 6 | Content Evaluation | Grounding / voice / positioning / repetition / quality gates | **PENDING** |
| 7 | Agent | Deterministic agent workflow and state combining all capabilities | **PENDING** |
| 8 | LinkedIn Tools | Clean integration layer around existing `Auth_handling/` OAuth | **PENDING** |
| 9 | Autonomous Execution | Trigger + publish gate enabling controlled autonomous publishing | **PENDING** |
| 10 | Observability & Memory | Publication history, decision audit, repetition prevention | **PENDING** |

## Milestones

1. **M1 — Foundations + corpus indexed**: Phase 1 + 2 complete. `data/` is
   queryable in ChromaDB with reliable metadata; ingestion is idempotent and
   tested.
2. **M2 — Evaluated retrieval + context**: Phase 3 + 4 complete. Retrieval is
   evaluated against a small gold set; the context builder produces grounded,
   structured prompts.
3. **M3 — Generate + evaluate**: Phase 5 + 6 complete. Candidate posts are
   generated and scored; nothing publishes without passing gates.
4. **M4 — Agent + LinkedIn tool**: Phase 7 + 8 complete. The Agent runs the
   full workflow and publishes through a controlled, authenticated tool.
5. **M5 — Autonomous + observable**: Phase 9 + 10 complete. Scheduled/manual
   autonomous execution with quality gates, full audit trail, and repetition
   protection.

## Migration From the Previous Plan

### Keep

- OpenRouter as the LLM interface
- Local `sentence-transformers/all-MiniLM-L6-v2` embeddings
- Chroma persistent vector store
- LangChain (LCEL) where useful
- Flask for the application interface/API
- Markdown files in `data/` as version-controlled source of truth
- The working LinkedIn OAuth implementation in `Auth_handling/`
- Modular, independently testable phases

### Change

| From (old plan) | To (this plan) |
|---|---|
| 4 flat data files (`projects.md`, `courses.md`, `career.md`, `voice.md`) | The existing structured `data/` hierarchy as the real knowledge base |
| Plain semantic retrieval (`search(q, k=5)`) | Metadata-aware retrieval with filters and retrieval evaluation |
| Simple `topic → LLM` generator | Context-aware generation subsystem fed by a branding context engine |
| No evaluation | Dedicated evaluation layer with mandatory quality gates |
| Human "Publish" button (always required) | Controlled autonomous publish capability behind a Publish Gate |
| Simple `/publish` route | LinkedIn tool abstraction with defined interface |
| No history | Publication memory and audit trail |
| One giant `PLAN.md` | `PLAN.md` roadmap + phase-specific docs in `docs/` |
| "RAG app" | "Autonomous Agent powered by RAG" |

### Add

- Evidence grounding (supported claims over plausible claims)
- Branding context builder (identity / evidence / positioning / voice / rules / current state)
- Quality gates and evaluation framework
- Agent state and deterministic workflow
- Tool abstraction (retrieve, generate, evaluate, publish, record)
- Autonomous execution with safeguards
- Observability and operational memory (separate from RAG knowledge)
- Security, failure handling, and recovery policy
- Testing at every architectural layer

## Course Alignment

This project remains a practical implementation of the IBM AI/RAG learning
path. Each phase document maps technologies to concepts being learned.

| Course topic | Where it appears |
|---|---|
| Document loading | Phase 2 — ingestion |
| Chunking | Phase 2 — ingestion |
| Embeddings | Phase 2 — vector representation |
| Chroma | Phase 2 — vector database |
| Similarity search | Phase 3 — retrieval |
| PromptTemplate | Phase 5 — generation |
| LCEL pipeline | Phase 5 — generation |
| OpenRouter | Phase 5 — LLM interface |
| Flask | Phase 1 / Phase 7 — application interface |
| Agent orchestration | Phase 7+ — later phases |
| Evaluation | Phase 6 — production-quality AI system |

Course-driven implementation and production-oriented extensions are both
explicitly called out in the phase documents.

## Definition of Done

The project is complete when all of the following hold:

- [ ] Knowledge ingestion works and is idempotent
- [ ] Retrieval is evaluated against a gold set
- [ ] Personal context is grounded in the knowledge base
- [ ] Posts follow the user's documented voice
- [ ] Personal claims are evidence-backed
- [ ] Generated posts are evaluated before publication
- [ ] The Agent can revise failed content
- [ ] LinkedIn integration works through a clean tool interface
- [ ] The Agent can publish through a controlled tool
- [ ] Publications are recorded in memory
- [ ] Duplicate/repetitive content is detectable
- [ ] Failures are observable and recoverable
- [ ] Tests cover core behavior at every layer
- [ ] Secrets are protected
- [ ] Architecture is documented

## Documentation Map

- Roadmap (this file): `PLAN.md`
- Docs index: `docs/README.md`
- Architecture: `docs/architecture/`
  - `system-overview.md`
  - `agent-architecture.md`
  - `rag-architecture.md`
  - `linkedin-integration.md`
  - `data-flow.md`
- Phases: `docs/phases/phase-01..phase-10`
- Evaluation: `docs/evaluation/` (`retrieval-evaluation.md`, `content-evaluation.md`, `quality-gates.md`)
- Decisions: `docs/decisions/ADRs/`
- Operations: `docs/operations/` (`local-development.md`, `environment.md`, `security.md`)

## How to Proceed

Work through the phases sequentially. Start with
`docs/phases/phase-01-foundation.md`. At every point, each phase document
answers: what we are building, why, what files change, what code should exist,
how it is tested, and what "done" means.