# Agent Architecture

## Role of the Agent

The Agent is the component that **decides what to do**. It composes the
project's capabilities — retrieval, context building, generation, evaluation,
revision, and publication — into a coherent workflow. The Agent is *not* a
single RAG chain; it is the reasoning layer that sits above RAG.

Two operating levels are supported:

### Level 1 — User-guided (simplest)

```text
User gives topic
    ↓
Agent retrieves personal context
    ↓
Agent generates post
    ↓
Agent evaluates post
    ↓
Agent optionally revises
    ↓
Agent publishes
```

### Level 2 — Autonomous (long-term target)

```text
Agent determines content opportunity
    ↓
Retrieves relevant personal knowledge
    ↓
Selects evidence
    ↓
Develops content angle
    ↓
Generates post
    ↓
Evaluates post
    ↓
Revises if necessary
    ↓
Publishes to LinkedIn
    ↓
Records publication
```

The first implementation targets **Level 1** with a deterministic workflow. A
bounded form of Level 2 (controlled content planning) is introduced in
Phase 9.

## Agent capabilities (tools)

The Agent can decide which capabilities to use:

```text
retrieve_knowledge()
build_context()
generate_post()
evaluate_post()
revise_post()
publish_to_linkedin()
record_publication()
```

Each is a thin, well-defined call. None of them "knows" about the Agent; the
Agent decides when to invoke them.

## Agent state

The Agent carries explicit state through a run:

```text
request
goal
retrieved_context
candidate_post
evaluation
revision_count
publish_decision
publication_result
```

State is held in a simple dataclass/struct (`app/agent/state.py`) and updated
step by step. Holding explicit state — rather than threading local variables
through ad-hoc code — makes the workflow testable and auditable.

## Workflow

The first implementation uses a **deterministic state machine** rather than an
open-ended agent. A fixed, explicit workflow is easier to test, safer, and
sufficient for the requirements.

```text
request
   │
   ▼
retrieve_knowledge ──► retrieved_context
   │
   ▼
build_context ──► structured_context
   │
   ▼
generate_post ──► candidate_post
   │
   ▼
evaluate_post ──► evaluation
   │
   ├── PASS ──► publish gate ──► publish_to_linkedin ──► record_publication
   │
   ├── REVISE (revision_count < MAX) ──► regenerate
   │
   └── REJECT ──► stop, record outcome
```

If generation, evaluation, or publication fails, the workflow follows the
failure policy (see `../operations/security.md` and `quality-gates.md`) instead
of continuing blindly.

## Deterministic vs LLM-based decisions

| Step | Nature |
|---|---|
| Retrieve / filter construction | Deterministic |
| Build context | Deterministic (assembly + rules) |
| Generate post | LLM-based |
| Grounding check | Deterministic (claim↔evidence) + optional LLM |
| Voice / positioning check | LLM-based |
| Repetition check | Deterministic (similarity/hash) |
| Publish gate decision | Deterministic policy over check results |
| Publish | Tool call (LinkedIn API) |
| Record publication | Deterministic |

## Policies

Policies (`app/agent/policies.py`) encode rules the workflow must not violate,
including:

- **Evidence grounding**: do not confidently assert a factual personal claim
  without supporting evidence. Prefer `supported claim` over `plausible claim`.
- **Revision limit**: cap `revision_count` (e.g., `MAX_REVISIONS = 2`).
- **Publish gate**: never publish a post that fails mandatory quality gates.
- **No false publish**: never report a post as published unless LinkedIn
  returned a success with a post id.
- **Duplicate protection**: never blindly retry a publish that may already
  have succeeded.

## Evolution path

The deterministic workflow may evolve to **LangGraph / explicit state machine**
later if the Agent genuinely needs conditional branching, sub-tasks, or
concurrency. Do not introduce this abstraction before Phase 7 demonstrates a
concrete need. LangChain LCEL is used for generation (Phase 5), not for the
Agent itself.

## Observability hook

Every state transition and decision is logged and, where relevant, recorded to
operational memory so the Agent's reasoning can be audited:

```text
decision → evidence → generation → evaluation → publication
```

## Files (target)

- `app/agent/agent.py` — top-level orchestration and public API
- `app/agent/state.py` — state dataclass/struct
- `app/agent/workflow.py` — the state machine / step sequence
- `app/agent/policies.py` — policy constants and rules

## Related documents

- System overview: `system-overview.md`
- End-to-end flow: `data-flow.md`
- Quality gates: `../evaluation/quality-gates.md`
- Phase: `../phases/phase-07-agent.md`