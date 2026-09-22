# Architecture Decision Records

Significant architectural decisions are recorded here so the reasoning behind
them survives. Use a lightweight template:

```markdown
# ADR-NNN — Title

## Status
Proposed | Accepted | Superseded by ADR-XXX

## Context
What prompted this decision.

## Decision
What we decided.

## Consequences
Trade-offs, follow-up work.
```

## Index

| ADR | Title | Status |
|---|---|---|
| ADR-001 | RAG is a capability of the Agent, not the Agent itself | Accepted (see `../architecture/system-overview.md`) |
| ADR-002 | Deterministic workflow/state machine before open-ended agent | Accepted (see `../architecture/agent-architecture.md`) |
| ADR-003 | Keep the existing `data/` hierarchy as the semantic knowledge base; do not flatten | Accepted (see `../architecture/rag-architecture.md`) |
| ADR-004 | Evidence grounding: supported claims over plausible claims | Accepted (see `../architecture/rag-architecture.md`, `../evaluation/quality-gates.md`) |
| ADR-005 | Operational memory kept separate from the RAG Chroma collection | Accepted (see `../phases/phase-10-observability-memory.md`) |
| ADR-006 | Freshness is read from `sync_checkpoints`, never re-derived or invented | Accepted (see `../architecture/data-flow.md` §3, `../architecture/system-overview.md` §4) |
| ADR-007 | Evidence is ranked by the corpus's own hierarchy, and positioning is separated from it rather than ranked | Accepted (see `../architecture/rag-architecture.md` §Evidence states and hierarchy) |

Additional ADRs should be added as the project evolves (e.g., choice of
LangGraph vs custom state machine, memory backend, scheduler design).