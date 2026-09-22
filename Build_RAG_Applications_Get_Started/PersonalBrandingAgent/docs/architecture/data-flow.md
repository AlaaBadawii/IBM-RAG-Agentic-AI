# Data Flow

## End-to-end view

```text
data/  (knowledge base, source of truth)
   │
   ▼
[Phase 2] Ingestion: discover → load → metadata → clean → chunk → embed → ChromaDB
   │
   ▼
[Phase 3] Retrieval: query interpretation → filter construction → semantic search → rerank
   │
   ▼
[Phase 4] Branding Context: evidence + positioning + voice + rules → structured context
   │
   ▼
[Phase 5] Generation: goal/topic + structured context → candidate post
   │
   ▼
[Phase 6] Evaluation: grounding / voice / positioning / repetition → PASS / REVISE / REJECT
   │
   ▼
[Phase 7] Agent workflow (state machine)
   │
   ▼
[Phase 8] LinkedIn tool: publish_to_linkedin(post_text)
   │
   ▼
[Phase 10] Memory / audit: record publication, decisions, sources
```

## Flow 1 — User-guided generation and publish (Level 1)

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

### Step detail

**1. Request** (`request`)

- Topic or goal from user (CLI, Flask API, or future scheduler).
- Optional constraints (length, language, angle).

**2. Retrieve** (`retrieved_context`)

- `retrieve_knowledge()` interprets the query, builds metadata filters
  (e.g., only `category=evidence`), runs semantic search, returns a structured
  retrieval result (documents + metadata + scores + filters used).

**3. Build context** (`structured_context`)

- The context builder (`app/context/builder.py`) consumes the retrieval result
  and assembles *named* sections. It does **not** concatenate raw documents
  into one blob, and it performs no retrieval of its own.
- The sections are the corpus's own categories, ordered by the evidence
  hierarchy (`../architecture/rag-architecture.md`): `repository_evidence`
  (the `@source/…` population), `evidence`, `completed_projects`,
  `in_progress_projects`, `certificates`, `in_progress_courses`,
  `stories_lessons`, `audit`, `unclassified` — plus the guidance sections
  `vision_goals`, `public_positioning`, `writing_style`.
- **Evidence and guidance are separate fields.** Positioning, voice and vision
  say how a supported fact is communicated; they are not support for a claim,
  and a separate field is what makes that impossible to misread downstream.
- Every item keeps its `source`, `chunk_id` and `evidence_state`; within a
  section, items are ordered by `(evidence state, source, chunk id)` — never by
  retrieval rank or score, which are carried as provenance only.
- Coverage is reported per section (count, evidence states present, emptiness).
  **No relevant evidence is a first-class outcome**, not an empty list: the
  result carries `INSUFFICIENT` rather than looking like a context that simply
  had nothing to say. A retrieval or state-store failure propagates — it is
  never degraded into "no evidence".
- Freshness comes from `sync_checkpoints` in the operational store, one entry
  per population. The layer reads it; it never re-derives it.

**4. Generate** (`candidate_post`)

- The prompt is assembled as separate labelled blocks — `TASK`, `EVIDENCE`,
  `COMMUNICATION GUIDANCE`, `CONSTRAINTS` — and the model is called through the
  repository's OpenRouter client. Step 8 implements this as a typed prompt value
  plus an injected client rather than an LCEL chain (`prompt | llm | parser`),
  which this line described before it was built; see the Step 8 deviations in
  `docs/implementation-status.md`.

**5. Evaluate** (`evaluation`)

- Grounding check (claims vs retrieved evidence), voice check, positioning
  check, repetition check, technical accuracy, specificity, unsupported-claims
  scan.
- Result: `PASS / REVISE / REJECT` with a score and reasons.

**6. Revise** (optional)

- If `REVISE` and `revision_count < MAX_REVISIONS`: regenerate with the
  evaluation feedback; increment `revision_count`.

**7. Publish gate** (`publish_decision`)

- Deterministic policy over the evaluation results. Reject any post failing a
  mandatory gate (see `../evaluation/quality-gates.md`).

**8. Publish** (`publication_result`)

- `publish_to_linkedin(post_text)` → `PublicationResult` with a LinkedIn post
  id on success. Never report published without a post id.

**9. Record** (`record_publication`)

- Append a record to operational memory: post id, topic, timestamp, retrieved
  sources, generated text, evaluation results, revision count, publication
  status, LinkedIn post id.

## Flow 2 — Autonomous content planning (Level 2, Phase 9 target)

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

The Agent reasons:

```text
What have I recently worked on?
What is interesting?
What demonstrates my positioning?
What have I not posted about recently?
What evidence is available?
What topic offers useful value to my audience?
```

Content planning is implemented as a **controlled capability** in Phase 9, not
fully autonomous open-ended behavior.

## Flow 3 — Failure paths

Failure behavior is defined explicitly per layer:

| Failure | Behavior |
|---|---|
| Retrieval failure (no useful evidence) | Do not confidently generate unsupported personal claims; report low-evidence and soften or abort |
| LLM failure | Retry per policy (bounded, backoff) or fail safely |
| Evaluation failure | Do not publish |
| LinkedIn API failure | Do not mark as published; classify error |
| Duplicate publication | Detect from history; avoid blind retries |
| Partial failure | Preserve enough state to recover or inspect |

See `../operations/security.md` (Failure handling) and the phase documents.

## Data stores

| Store | Contents | Backend |
|---|---|---|
| `data/` | Personal knowledge (source of truth) | Markdown, version-controlled |
| `chroma_db/` | Vector embeddings of `data/` | Chroma (persistent) |
| Operational memory | Posts, decisions, evaluations, publication history | Simple persistence (JSON/SQLite) — **separate** from Chroma |

## Audit trail

Every run records the full path a post took:

```text
decision → evidence → generation → evaluation → publication
```

This is what makes the Agent auditable when it performs external actions.

## Related documents

- System overview: `system-overview.md`
- Agent: `agent-architecture.md`
- RAG: `rag-architecture.md`
- LinkedIn: `linkedin-integration.md`
- Quality gates: `../evaluation/quality-gates.md`