# Documentation

This directory is the home of the **Personal Branding Agent** project
documentation. It deliberately separates the concerns that the old `PLAN.md`
mixed together:

- **Architecture** — how the system is designed.
- **Phases** — the implementation roadmap, one document per phase.
- **Evaluation** — how we measure retrieval, content, and quality gates.
- **Decisions** — architecture decision records (ADRs).
- **Operations** — local development, environment, and security.

`PLAN.md` (in the repository root) is the high-level roadmap and status tracker.
It links into this directory; it does not duplicate the detailed content.

## Structure

```text
docs/
├── README.md                      # This index
├── architecture/                  # System design
│   ├── system-overview.md         # Top-level architecture
│   ├── agent-architecture.md      # Agent responsibilities, workflow, state, tools
│   ├── rag-architecture.md        # Ingestion, metadata, embeddings, Chroma, retrieval
│   ├── linkedin-integration.md    # OAuth, LinkedIn tool, publishing, security
│   └── data-flow.md               # End-to-end flow: knowledge → post → audit
├── phases/                        # Implementation roadmap
│   ├── phase-01-foundation.md
│   ├── phase-02-ingestion.md
│   ├── phase-03-retrieval.md
│   ├── phase-04-branding-context.md
│   ├── phase-05-generation.md
│   ├── phase-06-evaluation.md
│   ├── phase-07-agent.md
│   ├── phase-08-linkedin-tools.md
│   ├── phase-09-autonomous-execution.md
│   └── phase-10-observability-memory.md
├── evaluation/
│   ├── retrieval-evaluation.md    # How to measure retrieval quality
│   ├── content-evaluation.md      # How to measure post quality
│   └── quality-gates.md           # PASS / REVISE / REJECT rules
├── decisions/
│   └── ADRs/                      # Architecture decision records
│       └── README.md
└── operations/
    ├── local-development.md       # Running the project locally
    ├── environment.md             # Env vars, secrets, dependencies
    └── security.md                # Security model for the Agent
```

## How to use this documentation

1. Read `../PLAN.md` first — it is the entry point and the status tracker.
2. Read `architecture/` to understand the target system.
3. Implement phase by phase, starting with `phases/phase-01-foundation.md`.
4. Consult `evaluation/` when implementing Phase 3 (retrieval evaluation) and
   Phase 6 (content evaluation).
5. Consult `operations/` for anything related to local setup, environment, or
   security.
6. Record significant architectural choices as ADRs under `decisions/ADRs/`.

## Documentation conventions

- Each phase document uses a **fixed template** (see
  `phases/phase-01-foundation.md` for the canonical structure).
- Acceptance criteria are **objectively testable**.
- Implementation status is recorded in `../PLAN.md`, not in the phase
  documents (phase documents describe the target state).
- Never document something as implemented unless it exists and works; use
  `Unknown / needs verification` where status is uncertain.