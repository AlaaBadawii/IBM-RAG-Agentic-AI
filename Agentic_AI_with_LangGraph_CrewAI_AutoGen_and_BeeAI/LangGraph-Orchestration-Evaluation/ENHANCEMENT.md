# ENHANCEMENT.md — Planned Enhancements

> **Status: PLANNED, NOT IMPLEMENTED.** This file documents two enhancements that
> have been designed but *not* implemented. All "proposed" content below describes
> future work; nothing in the production code, prompts, graph definitions,
> configuration, or tests has been changed to realize it. The **Current
> Architecture** section describes verified, existing behavior only.

---

## 1. Purpose and Scope

This document describes two planned enhancements to the LangGraph lab
`LangGraph-Orchestration-Evaluation`:

1. **Enhancement 1 — Final Output Validation and Targeted Repair** for the
   Orchestrator-Worker workflow in `01-parallel-meal-planning/`.
2. **Enhancement 2 — Explicit Approval State and Safe Iteration-Limit Handling**
   for the Reflection workflow in `02-investment-advisor-reflection/`.

The lab is organized as two independent, runnable projects (see root `README.md`):

| Project | Pattern | Entry point |
| --- | --- | --- |
| `01-parallel-meal-planning/` | Orchestrator-Worker (parallel meal planning) | `agent.py` → `orchestrator_worker` |
| `02-investment-advisor-reflection/` | Reflection / Evaluator-Optimizer (investment advisor) | `agent.py` → `optimizer_workflow` |

**Scope note / discrepancy with the task framing.** The enhancement request was
written as if both patterns lived in one codebase ("At
01-parallel-meal-planning"). In the actual repository the Orchestrator-Worker
pattern is implemented in `01-parallel-meal-planning/`, while the Reflection
pattern (which Enhancement 2 targets) is implemented in the sibling project
`02-investment-advisor-reflection/`. This document therefore assigns each
enhancement to the project that actually contains the relevant pattern. Both
enhancements are confined to their respective projects; neither requires changes
to shared utilities (`llm.py`, `print_workflow_info.py`).

Out of scope: refactoring existing code, changing prompts, changing the model
provider (`llm.py`), or altering the offline test harness's design.

---

## 2. Current Architecture (verified)

### 2.1 Project 1 — Orchestrator-Worker (`01-parallel-meal-planning/`)

**State** (`state.py`):

```python
class OrchestrationState(TypedDict):
    meals: str                                                  # free-text user request
    sections: list[Dish]                                        # orchestrator output
    completed_menu: Annotated[list[str], operator.add]          # parallel worker outputs
    final_meal_guide: str                                       # synthesizer output

class WorkerState(TypedDict):
    section: Dish                                               # one dish per worker execution
    completed_menu: Annotated[list, operator.add]               # reducer-merged into main state
```

**Schemas** (`schemas.py`): `Dish` (`name`, `ingredients: list[str]`, `location`)
and `Dishes` (`sections: list[Dish]`). Note that `Dish` carries **no dietary,
budget, or convenience fields** — the user request exists only as the free-text
`meals` string.

**Graph** (`graph.py`, compiled as `orchestrator_worker`):

```
START ──> orchestrator ──(assign_workers, Send fan-out)──> chef_worker (×N, parallel) ──> synthesizer ──> END
```

- `orchestrator.py` — invokes `planner_pipe`
  (`dish_prompt | llm.with_structured_output(Dishes)` from `pipe.py`/`prompt.py`)
  and returns `{"sections": [...]}`; tolerates dict-shaped planner output.
- `assign_workers.py` — conditional-edge function returning
  `[Send("chef_worker", {"section": s}) for s in state["sections"]]`.
- `chef_worker.py` — each parallel execution invokes `chef_pipe`
  (chef persona prompt → plain LLM) and returns
  `{"completed_menu": [meal_plan.content]}`, merged via `operator.add`.
- `synthesizer.py` — **not a model call**: it deterministically joins
  `state["completed_menu"]` with `"\n\n---\n\n"` and stores the result in
  `final_meal_guide`.

**Verified current behavior relevant to Enhancement 1:**

- The `synthesizer` performs no validation; it concatenates whatever the
  workers produced. Worker outputs are opaque strings (`meal_plan.content`);
  the structured `Dish` ingredients are passed to the chef prompt but the
  structured per-dish results are *not* retained alongside the prose output in
  a machine-comparable form (`completed_menu` holds `list[str]`).
- The user request (`meals`) and any shared constraints it contains (dietary
  restrictions, budget, etc.) are not stored in a constraint-structured form
  and are not re-consulted after synthesis.
- There is no node after `synthesizer`; the edge `synthesizer → END`
  (`graph.py:32`) terminates unconditionally. An inconsistent or
  constraint-violating final guide is returned as-is with no status field.
- There is no repair path: the conditional edges exist only on
  `orchestrator → chef_worker`, and once workers run the graph is linear.

**Existing tests** (offline, `tests/`): `test_s1_schemas.py` (schemas, reducers,
dummy state) and `test_s1_workflow.py` (node behavior with fake pipes, `Send`
fan-out, graph node/edge structure, end-to-end runs with fake pipes including
the zero-sections case).

### 2.2 Project 2 — Reflection (`02-investment-advisor-reflection/`)

**State** (`state.py`):

```python
class ReflectionState(TypedDict):
    investment_plan: str
    investor_profile: str
    target_grade: grades
    feedback: str
    grade: grades
    n: int
```

`grades` (`schemas.py`) is `Literal["ultra-conservative", "conservative",
"moderate", "aggressive", "high risk", "MISSING"]` — the `"MISSING"` sentinel
is a non-notebook addition used for routing defaults.

**Graph** (`graph.py`, compiled as `optimizer_workflow`):

```
START ──> determine_target_grade ──> investment_plan_generator ──> evaluate_plan
            │                                                    │ conditional (route_investment)
            │        ┌───────────────────────────────────────────┤
            │        └── "Rejected + Feedback" ──> investment_plan_generator (loop)
            └── "Accepted" ──> END
```

- `determine_target_grade.py` — `grade_pipe` picks the target risk grade from
  the investor profile (plain-text output, lowercased; no structured output).
- `investment_plan_generator.py` — two-phase generator: `cathie_wood_pipe` for
  the initial plan (no feedback), `ray_dalio_pipe` for revisions (feedback
  present).
- `evaluate_plan.py` — `buffett_evaluator_pipe`
  (`evaluator_prompt | llm.with_structured_output(Feedback)`) returns
  `{"grade", "feedback", "n": state.get("n", 0) + 1}` — the counter increments
  on every evaluation.
- `route_investment.py` — conditional routing function (default
  `iteration_limit=5`):
  - grades match (`current_grade == target_grade`) → `"Accepted"`
  - `state["n"] > iteration_limit` → **also `"Accepted"`** (`route_investment.py:22-24`)
  - otherwise → `"Rejected + Feedback"`

  The mapping in `graph.py:26-30` sends `"Accepted" → END` and
  `"Rejected + Feedback" → investment_plan_generator`.

**Verified current behavior relevant to Enhancement 2:**

- **The defect described by Enhancement 2 exists and is confirmed.** When the
  iteration limit is reached while grades do not match, `route_investment`
  returns `"Accepted"` anyway (`route_investment.py:22-24`), so the graph
  terminates through the *same* `"Accepted" → END` mapping used for an
  approved result. There is no state field distinguishing approval from
  limit-exhaustion.
- `ReflectionState` has **no approval/status field**; nothing in the final
  state records whether evaluation passed. The caller (`agent.py`) prints the
  final plan unconditionally.
- The existing tests encode this behavior as-is, not as a requirement:
  - `test_s2_workflow.py::TestEndToEndOffline::test_iteration_limit_stops_the_loop_gracefully`
    asserts the loop stops at `n == 6` (limit 5, `n > 5` triggers stop) with
    the *last rejected* plan (`grade == "moderate"`, `"Revised plan"`).
  - `test_s2_components.py::TestRouteInvestment::test_routing_table`
    parametrizes `n=6` with mismatched grades → `"Accepted"`.
  Both tests would need updating when Enhancement 2 changes the routing
  contract; they currently document the ambiguous behavior.
- The 02 README already flags related caveats (plain-text `grade_pipe` output
  can fail to match and drive the loop to the limit) but does not address the
  approval ambiguity.

**Existing tests** (offline, `tests/`): `test_s2_components.py` (schemas,
target grade, generator, evaluator, router) and `test_s2_workflow.py` (graph
structure, offline end-to-end runs).

### 2.3 Test conventions (applies to both)

- `pytest.ini` sets `testpaths = tests`; the suite runs entirely offline.
- `tests/conftest.py` loads each project's modules in dependency order via
  `importlib` under bare module names (`s1_modules`/`S2_MODULES` lists),
  replaces `llm.get_llm` with a `DummyLLM` that raises on any model call, and
  exposes `s1`/`s2` session fixtures (namespaces of each project's modules).
- Tests substitute fake pipes at the module-attribute seam, e.g.
  `s1.orchestrator.planner_pipe = fake`, `s2.evaluate_plan.buffett_evaluator_pipe = fake`,
  and run full `graph.invoke(...)` end-to-end with those fakes.
- Graph-structure assertions use `app.get_graph().nodes` and
  `app.get_graph().edges`.

Any new tests should follow these conventions exactly (offline fakes, no live
model calls). Note: `conftest.py` loads an explicit module list per project —
**new modules added by these enhancements must be appended to the
corresponding `*_MODULES` tuple** (e.g. `validator` after `synthesizer` for S1)
so they load in dependency order. This is a test-harness change, not a
production change, and is listed in each enhancement's implementation steps.

---

## 3. Enhancement 1 — Final Validation and Targeted Repair
**Target: `01-parallel-meal-planning/`**

### 3.1 Current behavior and verified limitations

Verified (see §2.1):

1. The final output (`final_meal_guide`) is produced by a pure string join in
   `synthesizer.py` and flows directly to `END` (`graph.py:32`). Nothing
   compares it against the original request (`state["meals"]`).
2. Worker outputs are unstructured strings; cross-section consistency
   (e.g., one chef assuming a vegetarian substitution while another uses beef
   for a shared dish set) cannot be detected by any existing component.
3. The user's shared constraints are not modeled: `meals` is a single
   free-text field and `Dish` has no constraint fields. Constraints live only
   inside the free text and inside each persona prompt's output behavior.
4. No status/failure reporting exists: every run ends at `END` with the
   synthesized text, valid or not.

### 3.2 Problem statement

Parallel workers produce individually reasonable outputs that, when combined,
can contradict each other or violate shared user requirements (e.g., a
"vegetarian menu" request where one dish plan includes chicken stock). The
synthesis step alone cannot guarantee consistency, because it only
concatenates. The workflow currently has no final check and no repair loop,
so invalid results are returned silently as if valid.

### 3.3 Proposed workflow and conditional-routing design

```
START ──> orchestrator ──(Send fan-out)──> chef_worker (×N) ──> synthesizer ──> final_validator
                                                                                 │ conditional (route_validation)
      ┌──────────────────────────────────────────────────────────────────────────┤
      └── "needs_revision" ──> orchestrator (revise pass)  ──> chef_worker (×K affected) ──> synthesizer ──> final_validator  (loop)
      └── "validated" ──> END
      └── "repair_exhausted" ──> END (explicit unapproved/failure status)
```

- New node `final_validator` (`final_validator.py`) runs **after**
  `synthesizer`. Edge changes in `graph.py`: `synthesizer → final_validator`
  replaces `synthesizer → END`.
- New conditional-edge function `route_validation` on `final_validator`
  returning at least: `"validated"` (→ `END`), `"needs_revision"`
  (→ `orchestrator`, or a dedicated revision-dispatch node), and
  `"repair_exhausted"` (→ `END` with an unapproved status).
- Repair routing should reuse the existing `Send` fan-out mechanism:
  `assign_workers` (or a sibling `assign_revisions` function) issues `Send`s
  **only for sections flagged in the validation result**, so unaffected
  worker outputs are never recomputed.
- Stale-result replacement: worker outputs must become keyed by section
  rather than append-only (see state changes) so that a repaired section
  *replaces* its old entry instead of `operator.add`-accumulating a
  conflicting second version. The simplest compatible approach is to switch
  `completed_menu` from `Annotated[list[str], operator.add]` to a
  dict-like/unique-keyed merge, or to have the synthesizer select the newest
  entry per section. This is the largest structural change in this
  enhancement and must be designed carefully (see trade-offs).

### 3.4 Proposed state changes and structured validation result

Add to `OrchestrationState`:

```python
class ValidationResult(BaseModel):      # new, in schemas.py
    passed: bool
    violations: list[Violation]         # hard-constraint breaches
    contradictions: list[Contradiction] # cross-section semantic conflicts
    affected_sections: list[str]        # section/dish identifiers (Dish.name is the natural key)
    repair_instructions: list[str]      # actionable per-section guidance
    # fields used by routing:
    repair_round: int                   # incremented per repair pass
```

```python
class OrchestrationState(TypedDict):
    meals: str
    shared_constraints: list[Constraint]   # NEW: extracted once, reused by validator
    sections: list[Dish]
    completed_menu: ...                    # merge semantics changed (see §3.3)
    final_meal_guide: str
    validation: ValidationResult           # NEW: last validation result
    repair_round: int                      # NEW (or kept inside ValidationResult)
    approved: bool                         # NEW: explicit final status
```

- `Constraint` (new schema) should distinguish `kind: "hard" | "preference"`;
  the validator treats violations of hard constraints as failures. A
  preference stated as mandatory by the user ("must be under $40 —
  non-negotiable") must be recorded as hard. Constraints are extracted once
  from `meals` by the orchestrator (deterministic parsing where possible,
  LLM-assisted extraction as a fallback) so every round validates against the
  same canonical list.
- `affected_sections` uses `Dish.name` as the section identifier; this is the
  only stable key currently available (noted as an open question: name
  collisions/renames across revisions).
- `approved: bool` gives the caller an explicit terminal status; when
  validation fails and the repair limit is reached, `approved` stays `False`
  and `final_meal_guide` is returned with the failure clearly recorded.

### 3.5 Validation strategy: deterministic vs. model-based

Not every check needs an LLM judge:

- **Deterministic checks (no model call):** presence of every requested dish
  in the output (string/keyword match against `sections`), ingredient-list
  membership for objective hard constraints that can be parsed from
  `meals`/`shared_constraints` (e.g., a literal "no peanuts" constraint →
  substring scan over retained structured ingredients), and count/section
  coverage. These require keeping the structured per-dish ingredients
  available at validation time (see state changes).
- **Model-based checks:** semantic contradictions across sections
  ("this section assumes a shared ingredient the other section omits"),
  soft-preference violations (budget tone, convenience framing), and overall
  coherence of the guide. Implemented as a new LLM pipe
  (e.g., `validator_pipe = validator_prompt | llm.with_structured_output(ValidatorJudgment)`)
  whose output is merged with the deterministic findings into the final
  `ValidationResult`.
- Rationale: deterministic checks are cheap, reliable, and rerunnable on every
  round; the model judge is reserved for what string matching cannot do.

### 3.6 Repair strategy and iteration limits

- Configurable `max_repair_rounds` (proposed default: 2, mirroring the spirit
  of S2's limit of 5 — exact default is an open question).
- On failure: `route_validation` → revision dispatch → `Send` fan-out for
  **only** `validation.affected_sections` → workers regenerate those sections
  with the repair instructions embedded in the worker prompt → synthesizer
  rebuilds the full guide → `final_validator` runs again.
- Unaffected, still-valid worker outputs are preserved by the keyed-merge
  change; repaired entries overwrite their predecessors.
- When `repair_round > max_repair_rounds`: terminate with
  `approved=False`, the last `ValidationResult`, and the (still-invalid)
  `final_meal_guide` explicitly flagged as unapproved. Never present an
  invalid result as validated.

### 3.7 Implementation steps (proposed)

1. `schemas.py`: add `Constraint`, `Violation`, `Contradiction`,
   `ValidationResult` (and the validator's structured-judgment schema).
2. `state.py`: extend `OrchestrationState` (`shared_constraints`,
   `validation`, `repair_round`, `approved`); change `completed_menu` merge
   semantics; extend `WorkerState` to carry the section key it corresponds to.
3. `orchestrator.py`: also emit `shared_constraints` extracted from `meals`.
4. New `final_validator.py` node + new validator pipe in `pipe.py` +
   validator prompt in `prompt.py`.
5. New `route_validation.py` conditional-edge function.
6. `assign_workers.py`: add revision-mode fan-out (filter sections by
   `validation.affected_sections`, inject repair instructions).
7. `synthesizer.py`: select latest per-section entries after the merge change.
8. `graph.py`: add `final_validator` node, replace `synthesizer → END` with
   `synthesizer → final_validator`, add conditional edges and the repair
   loop edges.
9. `tests/conftest.py`: append new module names to `S1_MODULES`.
10. New tests in `tests/` (see §3.8); existing `test_s1_workflow.py` graph
    structure tests must be updated for the new node/edges.

### 3.8 Testing strategy (planned scenarios, offline fakes)

Following the existing conventions (fake pipes, `graph.invoke`, node/edge
assertions):

| # | Scenario | Expected (proposed) |
| --- | --- | --- |
| 1 | All workers' outputs satisfy all constraints | Validator returns `passed=True`; `"validated"` → `END`; `approved=True`; zero repair rounds |
| 2 | Hard-constraint violation (e.g., allergen present despite "no peanuts") | Detected deterministically; `passed=False`; violation names the affected section |
| 3 | Contradiction between two sections (semantic) | Model-judge fake reports a cross-section contradiction; both affected sections listed |
| 4 | Two of three sections flagged | `Send`s issued only for the two affected sections; valid section's pipe is not re-invoked (fake call count asserts this) |
| 5 | Repaired section replaces stale output | After repair, `completed_menu`/guide contains only the repaired version for that section (no duplicate) |
| 6 | Revalidation after repair | Full output validated again each round; `validation` reflects the latest round |
| 7 | Validator fails every round | Loop stops after `max_repair_rounds`; final state has `approved=False` and the last `ValidationResult` |
| 8 | Limit exhaustion never yields success | Assert `approved is False` and routing returned `"repair_exhausted"` on the final round — never `"validated"` |

Unit-level: `route_validation` routing table (parametrized, mirroring
`test_s2_components.py::TestRouteInvestment`), validator-node behavior with
fake deterministic + fake model judges, and constraint-extraction behavior of
the orchestrator. **No tests have been run; these are planned scenarios.**

### 3.9 Benefits, risks, and trade-offs

**Benefits:** catches cross-section inconsistency that no existing component
can see; gives callers an explicit pass/fail; targeted repair keeps cost
proportional to the problem size; deterministic checks are free and stable.

**Costs / risks:**

- **Extra model calls:** one validator judge per round plus revised worker
  calls. With limit `k` and worst-case all-sections repair, worst case is
  roughly `1 + (k+1)` validation calls and up to `k+1` full worker fan-outs.
- **Latency:** validation serializes after synthesis; repair loops multiply
  total wall time.
- **State complexity:** changing `completed_menu` from `operator.add` to a
  replace-by-key merge touches the reducer contract relied on by
  `WorkerState`, `chef_worker`, the synthesizer, and several existing tests.
  This is the riskiest change; an alternative (synthesizer-side
  "latest per key" selection) keeps the reducer but pushes complexity into
  the synthesizer.
- **Repeated repair failure:** a validator that keeps rejecting (e.g., a
  contradictory hard constraint in the request itself) will always exhaust
  the limit; the design must treat that as a *valid, reported* failure, not a
  crash.
- **False positives from the model judge** could trigger unnecessary repair
  rounds; the deterministic layer should absorb the objective checks so
  judge output is never the sole basis for a hard-constraint failure.
- **Section identity:** `Dish.name` is a weak key (renames/collisions across
  revisions are possible).

---

## 4. Enhancement 2 — Explicit Approval State and Safe Termination
**Target: `02-investment-advisor-reflection/`**

### 4.1 Current behavior and verified limitations

Verified (see §2.2):

- `route_investment.py:22-24` returns `"Accepted"` when
  `state["n"] > iteration_limit`, **regardless of grade match**. Both approval
  and limit-exhaustion route to `END` via the same `"Accepted"` mapping in
  `graph.py:26-30`.
- `ReflectionState` contains no field recording whether the output was
  approved; `n` counts evaluations, and `grade`/`feedback` hold the last
  evaluation but nothing distinguishes "approved" from "gave up".
- Consequently the final state of a limit-exhausted run is indistinguishable
  from a successful one to any programmatic consumer. `agent.py` prints the
  final plan as a success either way.
- Existing tests document the ambiguous behavior (`test_s2_workflow.py:103-111`,
  `test_s2_components.py:146-167`) but do not treat it as intended.

This is a **confirmed defect**, verified in source and in the test table — not
an assumption.

### 4.2 Problem statement

The generation–evaluation cycle has an iteration limit. If the limit is
reached while the evaluator still rejects the plan, the graph terminates and
the last rejected output exits through the same path as an approved output,
with no state signal distinguishing the two. Callers cannot tell successful
completion from mere termination ("stopped" ≠ "approved").

### 4.3 Proposed state and routing changes

**Smallest appropriate state change** — add two fields to `ReflectionState`
(no duplication, no restructuring):

```python
class ReflectionState(TypedDict):
    investment_plan: str
    investor_profile: str
    target_grade: grades
    feedback: str
    grade: grades
    n: int
    approved: bool        # NEW: True only when evaluation matched the target
    terminated_on: str    # NEW (optional, recommended): "approved" | "iteration_limit"
```

- `approved` is set **only** by the routing decision, not by any node's
  implicit behavior: when `grade == target_grade`, the router records
  `approved=True`; otherwise `approved=False`.
- `terminated_on` records *why* the graph stopped, keeping `approved`
  unambiguous even in the exhausted case. (If minimalism is preferred,
  `approved` alone suffices; see open questions.)

**Routing change** (`route_investment.py`): replace the limit branch's
`return "Accepted"` with a distinct outcome, keeping the limit intact:

```python
if match:
    return "Approved"                       # was "Accepted"
elif state["n"] > iteration_limit:
    return "IterationLimitReached"          # was "Accepted"  ← the defect
else:
    return "Rejected + Feedback"            # unchanged
```

**Graph mapping change** (`graph.py:26-30`):

```python
add_conditional_edges(
    "evaluate_plan",
    route_investment,
    {
        "Approved": END,
        "IterationLimitReached": END,
        "Rejected + Feedback": "investment_plan_generator",
    },
)
```

**Setting the state fields:** the router is a conditional-edge function and
should not mutate state; the cleanest minimal options are (a) have
`evaluate_plan` compute `approved` alongside `grade`/`feedback` (it already
knows `target_grade`), or (b) move the decision into a tiny final node per
exit branch. Option (a) is recommended as the smallest change consistent with
the intent (see open questions).

**Caller-facing failure:** recommendation — return the final state with the
explicit status fields, matching the existing architecture (nodes return
dicts merged into state; `invoke` returns the final state; nothing raises
today). Raising an exception (e.g., a custom `IterationLimitError`) is
rejected as a default because it would change the error contract of every
`invoke` call and does not fit the current return-based style; callers who
want exceptions can check `state["approved"]`. This keeps `agent.py` a simple
state printer while making it print approval status explicitly.

### 4.4 Expected behavior (proposed)

| Evaluation outcome | Retries left? | Behavior |
| --- | --- | --- |
| `grade == target_grade` | — | Router → `"Approved"` → `END`; `approved=True`, `terminated_on="approved"` |
| `grade != target_grade` | yes (`n <= limit`) | Router → `"Rejected + Feedback"` → generator revises → re-evaluate |
| `grade != target_grade` | no (`n > limit`) | Router → `"IterationLimitReached"` → `END`; `approved=False`, `terminated_on="iteration_limit"`; last rejected plan retained in state but explicitly unapproved |

- Approval is never inferred from graph termination; it is recorded only by
  the routing decision.
- The iteration limit is preserved unchanged as the anti-infinite-loop
  safeguard; only the *exit status* of exhaustion changes.

### 4.5 Implementation steps (proposed)

1. `state.py`: add `approved: bool` (and optionally `terminated_on: str`) to
   `ReflectionState`.
2. `evaluate_plan.py`: compute and return `approved = (grade == target_grade)`
   with the existing fields (plus `terminated_on` if adopted).
3. `route_investment.py`: rename outcomes to `"Approved"` /
   `"IterationLimitReached"` / `"Rejected + Feedback"` and route on `approved`
   (or keep grade-comparison in the router — exactly one source of truth; see
   open questions).
4. `graph.py`: update the conditional-edge mapping; both non-rejected
   outcomes map to `END`.
5. `agent.py`: print `approved` / `terminated_on` in
   `pretty_print_final_state`.
6. Update existing tests that encode the old contract:
   `test_s2_components.py::TestRouteInvestment::test_routing_table` (the
   `n=6 → "Accepted"` row and the renamed outcomes) and
   `test_s2_workflow.py::TestEndToEndOffline::test_iteration_limit_stops_the_loop_gracefully`
   (now assert `approved=False` at `n == 6`).

### 4.6 Testing strategy (planned scenarios, offline fakes)

| # | Scenario | Expected (proposed) |
| --- | --- | --- |
| 1 | First evaluation matches target | `END` on first pass; `approved=True`; `n == 1`; plan unchanged from initial generator |
| 2 | Rejection with retries remaining | Loop through generator; next evaluation runs; `approved` stays `False` until a match |
| 3 | Evaluator never agrees | Terminates at `n == limit + 1` (current empirical bound: 6 with limit 5); `approved=False`, `terminated_on="iteration_limit"` |
| 4 | Rejected output never reported approved | Every state in which `grade != target_grade` has `approved is False` — asserted on the *final* state of the exhausted run |
| 5 | Termination within bound | For scripted evaluator sequences, the graph always terminates with `n <= limit + 1` (no infinite loop; limit behavior unchanged) |

Unit-level: parametrized routing table for the three outcomes (extending the
existing `TestRouteInvestment` pattern), and `evaluate_plan` unit test for the
new `approved` computation. All offline with fake pipes, per existing
conventions. **No tests have been run; these are planned scenarios.**

### 4.7 Benefits, risks, and trade-offs

**Benefits:** removes the success/termination ambiguity with a two-field
state addition and a routing-branch rename; callers get a machine-readable
status; the iteration-limit safeguard is preserved; changes are minimal and
localized to `state.py`, `evaluate_plan.py`, `route_investment.py`,
`graph.py`, and `agent.py`.

**Costs / risks:**

- Two exit branches now map to `END`; any future logging/graph rendering
  must distinguish them (the `terminated_on` field mitigates this).
- Dual bookkeeping risk: if `approved` is computed in `evaluate_plan` while
  the router independently compares grades, the two could diverge; the
  design must keep a single source of truth (open question).
- Test-contract churn: two existing tests encode the old behavior and must
  be updated (that is expected and desirable — they document a defect).
- The existing caveat that plain-text `grade_pipe` output may not equal a
  canonical grade (02 README) means limit-exhaustion is the *common* path in
  practice; the explicit failure status makes that visible rather than
  masking it.

---

## 5. Implementation Order and Dependencies

**Recommended order: Enhancement 2 first, then Enhancement 1.**

1. **Enhancement 2 first.** It is small, self-contained (one project, five
   files plus tests), and establishes the pattern both enhancements need:
   an explicit terminal-status field (`approved`) with a distinct
   limit-exhaustion exit. Its routing-table rename ("Accepted" → "Approved")
   also removes confusing naming before Enhancement 1 introduces its own
   routing vocabulary ("validated" / "needs_revision").
2. **Enhancement 1 second.** It is the larger change (new node, new routing
   function, reducer-merge semantics, constraint extraction) and can reuse
   the "explicit status, never fake success" contract proven by
   Enhancement 2 — its `approved: bool` field has the same purpose.

**Independence:** the two enhancements touch disjoint projects and disjoint
graph/state definitions; they can be implemented independently and in either
order. There is no shared code dependency — `llm.py` and `print_workflow_info.py`
are unchanged by both.

**Shared concerns / interactions:**

- Both add an `approved` terminal-status field; if consistency across the lab
  matters, a small shared convention (same field name and semantics) should
  be documented in the root `README.md` — a documentation change, not code.
- Both require adding modules to the `conftest.py` module lists
  (`S1_MODULES` for Enhancement 1; nothing new for Enhancement 2, which adds
  no new module files).
- Both change existing test expectations; test updates should land in the
  same change as the behavior change to keep the suite green.

---

## 6. Acceptance Criteria

### Enhancement 1 (measurable against the planned tests in §3.8)

- [ ] The compiled graph contains a `final_validator` node between
      `synthesizer` and `END`, verifiable via `get_graph()` structure tests.
- [ ] A valid output terminates with `approved=True` and no repair round run.
- [ ] A hard-constraint violation produces `passed=False` with the affected
      section identified, regardless of the model judge (deterministic check
      catches it).
- [ ] A cross-section contradiction reported by the validator is surfaced in
      `validation.contradictions` with both sections identified.
- [ ] When only some sections are affected, only those sections' workers are
      re-invoked (fake-pipe call counts prove unaffected pipes were not called).
- [ ] Repaired outputs replace, not accumulate: the final guide contains
      exactly one entry per section after repair.
- [ ] Every repair round is followed by full revalidation; the final
      `validation` field always reflects the last round.
- [ ] With validation failing every round, the loop stops after the
      configured `max_repair_rounds` and final state has `approved=False`.
- [ ] No path exists in which `approved=True` while `validation.passed is
      False`.

### Enhancement 2 (measurable against the planned tests in §4.6)

- [ ] Evaluation match terminates with `approved=True` and
      `terminated_on="approved"`.
- [ ] A rejection with retries remaining routes to the generator and loops.
- [ ] Reaching the iteration limit without a match terminates with
      `approved=False` (and `terminated_on="iteration_limit"` if adopted).
- [ ] No code path sets `approved=True` when `grade != target_grade`.
- [ ] For any scripted evaluator sequence, the graph terminates with
      `n <= iteration_limit + 1`.
- [ ] `route_investment` no longer returns `"Accepted"` for the
      limit-exhaustion branch (verified by the updated routing-table test).

---

## 7. Open Questions and Decisions

Recorded unresolved design choices:

1. **Enhancement 1 — merge semantics for repaired results.** Change the
   `completed_menu` reducer to a keyed/replace merge, or keep
   `operator.add` and have the synthesizer select the latest entry per
   section? The reducer change is cleaner but touches the widest surface
   (including `WorkerState` and existing reducer tests); the synthesizer-side
   selection preserves the reducer contract but centralizes dedup logic
   outside LangGraph's merge machinery.
2. **Enhancement 1 — section identity key.** `Dish.name` is the only stable
   identifier currently available. Should a synthetic section `id` be added
   to `Dish`/`Section` to make repair targeting robust against name changes?
   Adds schema surface; deferred until a concrete rename/collision scenario
   appears.
3. **Enhancement 1 — where constraints are extracted.** Extracting
   `shared_constraints` inside the orchestrator node (recommended for
   round-to-round consistency) versus a separate pre-node. A separate node
   is architecturally cleaner but adds a graph node and a model call.
4. **Enhancement 1 — repair dispatch target.** Route `"needs_revision"`
   back to `orchestrator` (which must detect repair mode from state) or to a
   dedicated `revision_dispatcher` node? The dedicated node avoids
   overloading `orchestrator` with two modes at the cost of one more node.
5. **Enhancement 1 — default `max_repair_rounds`.** Proposed 2; whether it
   should be a `graph.compile(configurable=...)` value, a module constant, or
   a parameter threaded through state is undecided.
6. **Enhancement 2 — single source of truth for approval.** Compute
   `approved` in `evaluate_plan` (recommended: smallest change) versus a tiny
   terminal node per exit branch, versus having the router compare grades.
   Exactly one of these must own the comparison; undecided which the team
   prefers.
7. **Enhancement 2 — `terminated_on` field.** Adopted in the proposal as
   optional; dropping it keeps the state even smaller but loses the
   explicit *reason* for termination. Decision deferred.
8. **Enhancement 2 — failure exposure.** Recommended returning the state
   with explicit status fields rather than raising; if downstream consumers
   of this lab eventually require exceptions (e.g., for orchestrating the
   workflow inside a larger system), revisit.
9. **Both — live-model verification.** Neither enhancement can be validated
   end-to-end against watsonx.ai without credentials; all verification in
   this lab is offline-by-design. A live `agent.py` run remains an open
   follow-up for both, matching the caveat style already used in the
   sub-project READMEs.
