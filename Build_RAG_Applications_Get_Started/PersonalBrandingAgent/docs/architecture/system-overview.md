# System Overview

## Purpose

The Personal Branding Agent generates, evaluates, revises, and publishes
authentic LinkedIn content on behalf of the user. Everything it says is
**grounded** in a personal knowledge base (`data/`), and every action it takes
is **auditable**.

## Design principles

1. **RAG is a capability, not the identity.** The Agent reasons, plans, and
   acts; RAG supplies grounded knowledge.
2. **Knowledge, reasoning, generation, evaluation, tools, execution, and
   observability are separated** so each can evolve independently.
3. **Evidence over plausibility.** Unsupported personal claims must not be
   published. The Agent prefers `supported claim` over `plausible claim`.
4. **Controlled autonomy.** Autonomous publishing exists, but only behind an
   explicit Publish Gate and quality gates.
5. **Progressive implementation.** Start simple (Python + LangChain + Chroma +
   OpenRouter + Flask + LinkedIn API + simple persistence) and add complexity
   only when a phase genuinely requires it. No multi-agent architectures,
   LangGraph, Redis, PostgreSQL, Kubernetes, message queues, or distributed
   workers up front.

## Conceptual architecture

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

## The seven concerns

| Concern | Responsibility | Primary module |
|---|---|---|
| **Knowledge** | Source-of-truth personal facts and evidence in `data/` | `data/` (version-controlled Markdown) |
| **Reasoning** | The Agent decides what to do and in what order | `app/agent/` |
| **Generation** | Produce candidate posts from structured context | `app/generation/` |
| **Evaluation** | Score posts against evidence, voice, positioning, repetition | `app/evaluation/` |
| **Tools** | Concrete external capabilities (publish, retrieve) | `app/integrations/`, `app/retrieval/` |
| **Execution** | Interfaces that trigger the Agent (CLI, Flask API, scheduler) | `app/api/`, CLI, scheduler |
| **Observability** | History, decisions, failures, audit trail | `app/memory/` |

## Layers in detail

### 1. Knowledge layer

- `data/` is the version-controlled source of truth: projects (completed and
  in-progress), courses, certificates, evidence with evidence states, stories
  and lessons, vision, writing style, public positioning, and audit records.
- The **directory hierarchy is meaningful** and is preserved (never flattened).
  Each top-level directory is a semantic category; `evidence/` further groups
  by domain (`ai/`, `backend/`, `devops/`, `learning/`, `professional/`,
  `projects/`).
- `data/audit/README.md` defines the evidence hierarchy and audit principles;
  `data/evidence/README.md` defines the evidence states. The system's evidence
  policy is derived from these files.

### 2. RAG layer

- Pipeline: Markdown discovery → document loading → metadata extraction →
  cleaning/normalization → chunking → embeddings → ChromaDB.
- Retrieval: semantic similarity + metadata filtering, with an optional
  reranking step and a structured retrieval result object.
- Chroma persists under `chroma_db/` (gitignored).

### 3. Agent reasoning layer

- A deterministic workflow (state machine) that composes capabilities in the
  correct order, holds state, and enforces policy.
- State: `request`, `goal`, `retrieved_context`, `candidate_post`,
  `evaluation`, `revision_count`, `publish_decision`, `publication_result`.
- Not an open-ended open-loop agent; bounded by policies and quality gates.

### 4. Branding context layer

- Builds the LLM prompt from *distinct* parts so the model cannot confuse them:
  - **Identity / stable facts** — who the user is
  - **Evidence** — what the user did, built, learned
  - **Positioning** — how the user wants to be perceived
  - **Voice / style** — how posts should sound
  - **Content rules** — what may and may not appear
  - **Current state** — what is being learned/built now

### 5. Generation layer

- LCEL chain (LangChain `prompt | llm | parser`) initially.
- Inputs: topic/goal, relevant evidence, current context, positioning, writing
  style, content constraints, and (later) previously published posts.

### 6. Evaluation layer

- Dimensions: factual grounding, authenticity, voice, positioning, technical
  accuracy, repetition, specificity, LinkedIn quality, unsupported claims.
- Quality gates produce `PASS / REVISE / REJECT`.
- Some checks are deterministic (repetition hash, grounding against retrieved
  evidence); others are LLM-based (voice, positioning).

### 7. Tools / integrations

- LinkedIn tool: `app/integrations/linkedin/` wraps the existing
  `Auth_handling/` OAuth code behind a clean interface
  (`publish_to_linkedin(post_text)`).
- Retrieval is exposed to the Agent as `retrieve_knowledge()`.

### 8. Execution interfaces

```text
Agent Core
     │
     ├── CLI
     ├── Flask API
     └── Future scheduler
```

The Flask UI is one interface to the Agent, not the Agent itself. The original
single-page UI is retained as a development/debugging interface.

### 9. Observability / memory

- RAG knowledge (long-term facts) and operational memory (posts, decisions,
  evaluations, failures) are **separate stores**.
- Publication history enables repetition prevention, content-gap detection,
  debugging, and autonomy auditing.

## Target repository layout

```text
PersonalBrandingAgent/
├── app/
│   ├── agent/            # agent.py, state.py, workflow.py, policies.py
│   ├── ingestion/        # loader.py, chunker.py, metadata.py, pipeline.py
│   ├── retrieval/        # retriever.py, filters.py, reranker.py
│   ├── context/          # builder.py, evidence.py, branding.py
│   ├── generation/       # generator.py, prompts.py
│   ├── evaluation/       # grounding.py, style.py, positioning.py, repetition.py, evaluator.py
│   ├── integrations/linkedin/  # client.py, auth.py, publisher.py
│   ├── memory/           # store.py, models.py
│   └── api/routes.py
├── data/                 # knowledge base (source of truth)
├── docs/                 # this documentation
├── tests/
├── chroma_db/            # vector store (gitignored)
├── templates/
├── Auth_handling/        # existing LinkedIn OAuth
├── PLAN.md
├── config.py
├── requirements.txt
└── .gitignore
```

The architecture describes the **target state**. Each phase introduces only the
files it needs.

## Guards against over-engineering

- LangChain LCEL is used for generation. Agent orchestration may evolve to
  LangGraph or an explicit state machine only when Phase 7 genuinely needs it.
- Operational memory starts as simple JSON/SQLite persistence — no database
  server required.
- No queue, worker, or event system until Phase 9 demonstrates a concrete need
  for one.

## Related documents

- Agent behavior: `agent-architecture.md`
- Knowledge and retrieval: `rag-architecture.md`
- LinkedIn: `linkedin-integration.md`
- End-to-end data flow: `data-flow.md`
- Roadmap and status: `../PLAN.md`