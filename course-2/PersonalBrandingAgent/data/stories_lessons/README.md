# Stories & Lessons

Reusable personal engineering stories that demonstrate how Alaa thinks, builds,
solves problems, and learns. These are **internal assets** for the Personal
Branding Agent — **not** LinkedIn posts. Each story follows a single structure
(Type, Context, Problem, What I Did, Decision/Insight, Result, Engineering
Lesson, Why This Matters, Evidence, Content Potential, Story strength).

Principles:

- Demonstrated ability over claims.
- A story is not a project summary — it captures a problem, a decision, a
  result, and a lesson.
- Honesty preserved from `../audit/cross_source_audit.md`
  (learning ≠ experience; Kubernetes stays in-progress; FlyRank/Alignerr
  conservative; no production claims without evidence).

## Story Index

| Story | File | Type | Main Theme | Strength | Evidence | Content Potential |
|-------|------|------|------------|----------|----------|-------------------|
| Most CI failures are environment, not code | [ci_failures_are_environment_not_code.md](ci_failures_are_environment_not_code.md) | Debugging | environment vs code | STRONG | jenkins-practice git log | Debugging lesson; "check environment first" |
| Containerized CI for reproducibility | [containerized_ci_for_reproducibility.md](containerized_ci_for_reproducibility.md) | DevOps / Production | reproducibility | STRONG | Jenkins Dockerfile | DevOps reproducibility post |
| I committed an SSH key to git | [committed_ssh_key_to_git.md](committed_ssh_key_to_git.md) | Failure / Mistake | credential hygiene | MEDIUM | Packt-DevOps-Bootcamp repo | Mistake / credential hygiene lesson |
| Never trust an LLM's arithmetic | [never_trust_llm_arithmetic.md](never_trust_llm_arithmetic.md) | AI Engineering | validate AI output | STRONG | evaluator_core | AI insight / verify with code |
| Dict keys are exact strings | [dict_keys_are_exact_strings.md](dict_keys_are_exact_strings.md) | Debugging | exact-match debugging | MEDIUM | evaluator_core PROGRESS | Short debugging lesson |
| Build the mechanics before a framework | [build_mechanics_before_frameworks.md](build_mechanics_before_frameworks.md) | Learning | learning-by-building | STRONG | LLMs/AI-Agents | "I built AI agents from scratch" |
| Test every AI step with a fake LLM | [test_every_ai_step_with_a_fake_llm.md](test_every_ai_step_with_a_fake_llm.md) | AI Engineering | test-driven AI | MEDIUM | evaluator_core tests | AI testing technique |
| Quizey exam versioning (copy-on-write) | [quizey_exam_versioning.md](quizey_exam_versioning.md) | Architecture | immutability & fairness | STRONG | exam_service.py | Architecture decision post |
| Quizey attempt state machine | [quizey_attempt_state_machine.md](quizey_attempt_state_machine.md) | Architecture | domain modeling | STRONG | state_machine.py | State machine engine |
| Quizey idempotency (exactly-once) | [quizey_idempotency.md](quizey_idempotency.md) | Engineering Decision | concurrency | STRONG | idempotency.py + concurrency test | Reliability/concurrency story |
| DB is source of truth for roles | [quizey_db_is_source_of_truth.md](quizey_db_is_source_of_truth.md) | Engineering Decision | auth/security | MEDIUM | rbac.py | Auth source-of-truth post |
| FastAPI: business logic out of routes | [fastapi_layers_not_routes.md](fastapi_layers_not_routes.md) | Engineering Decision | layering/architecture | MEDIUM | fastapi_shipment_api | Architecture learning story |
| Kubernetes: first manifest had typos | [kubernetes_first_step_typos.md](kubernetes_first_step_typos.md) | Learning | honest early learning | WEAK | kubernetes_manara_lab | Honest in-progress journey |

## Story Inventory

### AI Engineering
- never_trust_llm_arithmetic.md
- test_every_ai_step_with_a_fake_llm.md

### Backend Engineering
- fastapi_layers_not_routes.md
- quizey_db_is_source_of_truth.md

### DevOps / Production
- containerized_ci_for_reproducibility.md

### Architecture / System Design
- quizey_exam_versioning.md
- quizey_attempt_state_machine.md
- quizey_idempotency.md

### Learning / Growth
- build_mechanics_before_frameworks.md
- kubernetes_first_step_typos.md

### Failures / Mistakes
- committed_ssh_key_to_git.md
- ci_failures_are_environment_not_code.md (debugging a recurring failure)
- dict_keys_are_exact_strings.md

## Strongest Content Candidates

1. **Never trust an LLM's arithmetic**
   - Interesting because it shows real AI-engineering judgment: deterministic math
     verified in code, not taken from the model.
   - Best angle: AI debugging / "verify LLM output with code".

2. **Quizey idempotency (exactly-once under concurrency)**
   - Interesting because it proves a reliability property with a concurrency
     harness — design + verification.
   - Best angle: engineering decision / reliability.

3. **Quizey exam versioning (copy-on-write)**
   - Interesting because a "simple edit" requirement became a fairness/product-
     integrity decision.
   - Best angle: architecture follows product priorities.

4. **Build the mechanics before a framework**
   - Interesting because it shows the learning process behind real agent work.
   - Best angle: learning-by-building / "I built AI agents from scratch".

5. **Most CI failures are environment, not code**
   - Interesting because it is a common pain point solved with real debugging
     persistence.
   - Best angle: debugging story / DevOps lesson.

6. **Quizey attempt state machine**
   - Interesting because modeling the domain as a state machine prevents a class
     of bugs up front.
   - Best angle: architecture / domain modeling.

7. **Test every AI step with a fake LLM**
   - Interesting because it is a transferable AI testing technique (cheap,
     deterministic).
   - Best angle: AI engineering technique insight.

## Candidates (feature or reject)

- **Quizey Postman caught bugs unit tests missed** (in-progress): real value —
  verification via manual API testing surfaced crash bugs. Evidence exists in
  quizey_v2.md. EVIDENCE_GAP: not yet a story file (needs the source detail
  documented). Consider adding.
- **Kubernetes**: keep as an honest early-learning story; do not upgrade.
- **Book/Marker/GenAI/other**: course-level; see `../evidence` — not personal
  decision stories unless a real problem/decision emerges.