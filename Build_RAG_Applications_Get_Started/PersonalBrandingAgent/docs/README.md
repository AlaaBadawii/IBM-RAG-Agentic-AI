# Documentation

This directory is the home of the **Personal Branding Agent** project
documentation. It deliberately separates the concerns that the old `PLAN.md`
mixed together:

- **Architecture** — how the system is designed.
- **Retrieval** — the retrieval milestone: concepts and measured results.
- **Evaluation** — how we measure retrieval, content, and quality gates.
- **Decisions** — architecture decision records (ADRs).
- **Operations** — local development, environment, and security.
- **Phases** — foundational phase documents (historical).

## Documentation roles

The two primary entry points have distinct jobs:

```text
../PLAN.md
→ master implementation roadmap. "What are we going to build?"

implementation-status.md
→ current implementation state and continuation point.
  "What has actually been built, verified, and where do we continue?"
```

Everything else:

```text
architecture/   → how the system is designed
decisions/      → architectural decisions and their reasoning
retrieval/      → retrieval-specific technical documentation
evaluation/     → evaluation results
operations/     → operational and deployment documentation
phases/         → historical/foundational phase documentation
```

`PLAN.md` is authoritative for the roadmap. `implementation-status.md` is
authoritative for **progress**. Neither duplicates the other.

## Structure

```text
docs/
├── README.md                      # This index
├── implementation-status.md       # Current implementation state + continuation point
├── architecture/                  # System design
│   ├── system-overview.md         # Top-level architecture
│   ├── agent-architecture.md      # Agent responsibilities, workflow, state, tools
│   ├── rag-architecture.md        # Ingestion, metadata, embeddings, Chroma, retrieval
│   ├── linkedin-integration.md    # OAuth, LinkedIn tool, publishing, security
│   └── data-flow.md               # End-to-end flow: knowledge → post → audit
├── retrieval/                     # Retrieval milestone (implemented)
│   ├── README.md                  # Index + the six strategies in one table
│   ├── semantic-vs-keyword.md
│   ├── metadata-filtering.md
│   ├── multi-query.md
│   ├── hybrid-reranking.md
│   └── evaluation.md              # Hit@K / MRR and what the numbers showed
├── phases/                        # Foundational phase documents (historical)
│   ├── phase-01-foundation.md
│   └── phase-02-ingestion.md
├── evaluation/                    # (empty — not yet written)
│   ├── retrieval-evaluation.md
│   ├── content-evaluation.md
│   └── quality-gates.md
├── decisions/
│   └── ADRs/
│       └── README.md              # Template + index (ADR files not yet written)
└── operations/                    # Written in Step 0
    ├── local-development.md       # Configuration authority, CLIs, tests
    ├── environment.md             # Python version, reproduction, resolved versions
    └── security.md                # Secret vs non-secret split
```

> Items marked *not yet written* are planned locations, not existing documents.
> Do not link to them as if they exist. `operations/` was written in Step 0 and
> its three documents exist; `evaluation/` remains planned.

## Roadmap and phase documents

`PLAN.md` was rewritten and now defines the roadmap as **Steps 0–14**. The
`phases/` documents predate that rewrite and describe an earlier phase plan.

- `phases/phase-01-foundation.md` and `phase-02-ingestion.md` remain accurate
  descriptions of what was built and are kept as historical reference.
- Phases 03–10 were never written and are **superseded** by `PLAN.md` Steps
  0–14. Do not create `phase-03.md` … `phase-10.md`.
- Per-step implementation records live in `implementation-status.md`, not in
  separate `step-NN.md` files.

## How to use this documentation

1. Read `../PLAN.md` first — it is the master roadmap and the entry point.
2. Read `implementation-status.md` to find where implementation currently
   stands and which step comes next.
3. Read `architecture/` to understand the target system.
4. Implement step by step, following `PLAN.md` §8. Start with Step 0.
5. Consult `retrieval/` for the retrieval layer that already exists.
6. Consult `evaluation/` when content evaluation and verification gates are
   implemented (Steps 9 and 13).
7. Consult `operations/` for anything related to local setup, environment, or
   security.
8. Record significant architectural choices as ADRs under `decisions/ADRs/`.

## Documentation conventions

- Each phase document uses a **fixed template** (see
  `phases/phase-01-foundation.md` for the canonical structure).
- Acceptance criteria are **objectively testable**.
- `PLAN.md` describes the **target state**; `implementation-status.md` records
  the **actual state**. Never conflate them.
- Implementation status is recorded in `implementation-status.md` — not in
  `PLAN.md`, and not in phase documents.
- Never document something as implemented unless it exists and works; use
  `Unknown / needs verification` where status is uncertain.
- Existing technical documentation is not rewritten for consistency alone. If a
  document becomes wrong, correct it where it is wrong rather than regenerating
  it.