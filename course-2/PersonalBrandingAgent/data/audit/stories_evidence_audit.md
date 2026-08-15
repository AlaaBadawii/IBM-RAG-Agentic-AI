# Stories → Evidence Audit

## Purpose

For each story in `data/stories_lessons/`, answer one question honestly: **can this
story be used as personal-branding material without overstating what actually
happened?** The audit checks every claim in a story against the actual source repos
and the KB evidence hierarchy (source/repo > `evidence/` > `completed_projects/` >
`in_progress_projects/`), and assigns a verdict.

The audit **created only**; no story was rewritten, and no claim was strengthened.

## Evidence Standard & Classes

Sources are ranked highest-first; a story file is never evidence for itself, and
this audit is not primary evidence.

- **STRONG** — source directly, verifiably documents the event (real file/commit/
  test with the exact detail).
- **SUPPORTED** — clear and first-hand, but partly indirect or not fully verified
  end-to-end.
- **WEAK** — plausible persona-event, but key details missing from the KB/source.
- **NEEDS_EVIDENCE** — real but unproven in the repo/KB; must be confirmed before
  publishing.
- **DO_NOT_USE** — unsupported, contradicted by evidence, misleading, or invented.

Special rule applied: distinguish a **personal event** (a bug/decision/tradeoff/
experiment) from **generic knowledge**. A story that merely repeats well-known
knowledge (e.g., "dict keys must match" as a general statement) is weak unless it is
tied to the concrete `tool-executed` vs `tool_executed` event Alaa actually hit.

Special rule applied: never unpack a lab/learning into production experience,
deployment from config, mastery from a course, or employment from a portfolio.

## Story-by-Story Audit

### DevOps

**1. `ci_failures_are_environment_not_code.md` — STRONG**

Verified against `/home/alaabadawii/DevOps/jenkins-practice/`:
- The `Jenkinsfile` (docker test stage) actually exists and shows `PYTHONPATH=. pytest` inside `python:3.10-slim`.
- `.github/workflows/ci.yml` uses `python -m pytest`.
- `tests/test_app.py` does `from app import app`.
- `git log` commit titles confirm the sequence ("Fix CI imports and clean pipeline", "Use python -m pytest in CI", "Fix PYTHONPATH for CI").

A first-hand multi-commit debugging event with a root-cause (import path / invocation)
and resolution in git history. Personal event closely tied to code. **Publicly safe**
as a debugging/CI lesson. This is genuinely STRONG.

**2. `containerized_ci_for_reproducibility.md` — SUPPORTED**

Evidence: the same `Jenkinsfile` shows the tests run inside `docker run --rm ... python:3.10-slim`, and `git log` includes "Fix CI using Docker instead of venv". The claim "switched the test stage to run inside an ephemeral container" is accurately documented.

Slight caution: the repo's final config (Docker test stage) is real, but the exact
owner of an "-- it was 3.10-slim" decision chain is implied rather than documented;
the outcome ("pipeline reproducible") is reasonable but not measured. Keep it honest
as a "what I chose and why", not "this objectively fixed flakiness for all time".
**SUPPORTED** — public safe with the container choice emphasis on the decision.

### AI / LLM

**3. `never_trust_llm_arithmetic.md` — STRONG**

Exact match to source. `evaluator_core/PROGRESS.md` ("Two real bugs hit and fixed", bug #2) states: Claude asserted `overall_score == 2.75` when the weighted average of `4, 2, 3, 4` at `0.25` each is `3.25`, caught by doing arithmetic by hand. The implementation detail is also consistent with `agents/judge.py` (`_compute_weighted_score`) and the Decisions log ("Overall score: weighted average computed in plain Python, not by the LLM").

A concrete, reproducible bug with hand-verifiable numbers and a clear engineering
decision. **PublicSafe** and directly reinforces the "verify LLM output with code"
identity. STRONG.

### 4. `dict_keys_are_exact_strings.md` — SUPPORTED

The specific `tool-executed` (hyphen) vs `tool_executed` (underscore) mismatch is
documented in `evaluator_core/PROGRESS.md` (bug #1) and in the Decisions Log
("Environment key naming ... Hit a real bug from a typo"). The mechanism (dictionary
keys / exact string match) is real and first-hand. This is a **personal event**, not
just generic "keys must match" knowledge.

Caution for public: the event is small; the story's "lesson" is only as interesting
as the debugging it actually demonstrates. It is honest and usable as a short post,
but it is not a headline. **SUPPORTED** — good as a short insight, MEDIUM strength.

### 5. `test_every_ai_step_with_a_fake_llm.md` — SUPPORTED

Verified: `core/llm.py` exposes `real_llm_call(prompt, schema, ...) -> dict` and
`tests/test_judge.py` has `fake_llm_call(prompt, schema) -> dict` injected via the
`ActionContext`/`Environment` (dependency injection). This is a real technique,
first-hand, and well evidenced.

Verdict: strong technique, but the story must not claim more than it is — it
demonstrates a **testing technique**, not a deployed production system. The claim
"tests run with zero API calls" is directly confirmed by the design. The story
honestly grades its own strength as MEDIUM. **SUPPORTED**.

### 6. `build_mechanics_before_frameworks.md` — STRONG

Matches `/home/alaabadawii/LLMs/AI-Agents/README.md` "What I Learned" (agent loop ~50
lines, memory-memory list, tool calling as a protocol, termination explicit) and the
folder artifacts (`Readme_Agent/`, `Agent_Assistant/`, `Multi_Agents/`,
`docker-compose.yml`). This is a deliberate engineering decision, concretely
artifacts.

Caution: this is a **learning/lab project**, NOT production. The story correctly
says "experimental/local work — not a production system." Keep that boundary; "three
working agents" ≠ "production-grade system". With that framing it is honest and
STRONG as a learning journey.

### 7. `fastapi_layers_not_routes.md` — SUPPORTED

Verified: FastAPI code (`/home/alaabadawii/FastAPI/app/main.py`) keeps routes thin
and typed (`schemas.py`, `database/session.py`), which is a real layering choice. The
insight that this mirrors the Quizey `Route→Service→Model` discipline is a fair
cross-project observation.

Honesty guard: the FastAPI is clearly a **practice lab** (no tests, no deployment,
sync SQLModel). The story says exactly that ("starter-grade … no tests"). Keep the
framing as a judgment/learning story, not experience. **SUPPORTED** but modest result.

### 8. `kubernetes_first_step_typos.md` — WEAK

Confirmable: `deployment.yaml` exists with misspelled `matchLables:` and `lables:`;
`commands.md`/`notes.md` are empty; `minikube-linux-amd64` present. So the specific
typographical bug the story describes is literally correct and honest.

But the whole thing is early learning with no applied/deployed result and little
demonstrated engineering judgment yet. The story itself grades itself WEAK and is
deliberately honest ("no failed cluster"). **WEAK** — fine as an honest "start of the
journey", not for a competency claim. Must remain framed as an honest starting point.

> Note: `containerized_ci_for_reproducibility.md` is covered under #2 above (same
> repo and decision as the CI story).

## Quizey (all four)

### 9. `quizey_exam_versioning.md` — STRONG

The story's claims are directly visible in the actual uncommitted Quizey V2 code:
- `app/services/exam_service.py` has `create_exam_version(...)` (copy-on-write,
  comment "Create a new version of a published exam"), `root_exam_id`,
  `publish_exam`, single-published version logic.
- Versioning (demote-on-publish, `(v{n})` suffix, 249-char cap) is a real product
  decision.

The only caveat: this sits in uncommitted work (HEAD `bc8f7f5`). For public use, avoid
implying it is already deployed/released; it is the current, designed behavior.
**STRONG** as designed & justified architecture, honesty: frame as
"the design I'm building", not "shipped".

### 10. `quizey_attempt_state_machine.md` — STRONG (with an accuracy alert)

Verification:
- `app/models/state_machine.py` implements `StateMachineMixin` with `@validates`
  guard and `ATTEMPT_TRANSITIONS` exactly as claimed (in_progress → {paused,
  submitted}, → submitted → graded → archived; illegal → `InvalidTransitionError`).
- `app/models/attempt.py` sets `TRANSITIONS = ATTEMPT_TRANSITIONS`.

**Accuracy alert**: the story claims "**24+ subtest coverage** in `test_state_machine.py`".
The actual file has **5 test functions** (which, via `subTest`, run a larger number of
assertions, but "24+" is not count-able from the file). The verifiable, defensible
claim is "5 state-machine test cases exercising the full transition matrix", not "24+
tests". Recommend correcting the number before publication; otherwise the
architecture claims are all verifiable. This is the only numeric discrepancy found in
this story. **STRONG** for architecture, with the test-count correction.

### 11. `quizey_idempotency.md` — STRONG

Verification matches exactly:
- `app/utils/idempotency.py`: `@idempotent` decorator, `Idempotency-Key` header, 409
  for in-flight (`Request already in progress`), TTL + stale-lock cleanup.
- `app/models/idempotency_key.py`: `UniqueConstraint` on (user,key,endpoint) + status.
- `tests/test_attempts/test_concurrency.py`: real race test "10 concurrent submits
  must yield exactly one 200" and helper `assert_exactly_one_success`.

Framing: the claim "exactly one graded attempt under concurrency" is verified at the
**test level** (the concurrency harness, "exactly one returns 200"), not necessarily
at the later full pipeline. Keep "proven in the harness/test" precise. STRONG.

### 12. `quizey_db_is_source_of_truth.md` — STRONG (with an honest open gap)

Verification: `app/utils/rbac.py` literally says "The database is the single source
of truth for a user's role" and reads `User.role` directly (not the JWT) and returns
403 `Insufficient permissions`. `auth_service` handles tokens. This matches exactly.

The story honestly discloses the open gap (re-audit every route, re-verify the 403
negative test — Milestone 2.1.4). Keep it; this is a decision story, not a fully
verified wide deployment. Fine as a strong, defensible auth decision.

## Summary Table

| Story | File | Verdict | Public note |
|---|---|---|---|
| CI failures are environment | `ci_failures_are_environment_not_code.md` | STRONG | — |
| Container CI reproducibility | `containerized_ci_for_reproducibility.md` | SUPPORTED | frame as a choice not a measured metric |
| SSH key committed | `committed_ssh_key_to_git.md` | **SEE RED FLAG** | see below |
| LLM arithmetic | `never_trust_llm_arithmetic.md` | STRONG | — |
| Dict keys exact strings | `dict_keys_are_exact_strings.md` | SUPPORTED | short post |
| Fake LLM testing | `test_every_ai_step_with_a_fake_llm.md` | SUPPORTED | technique, not prod |
| Build mechanics | `build_mechanics_before_frameworks.md` | STRONG | learning, not prod |
| FastAPI layers | `fastapi_layers_not_routes.md` | SUPPORTED | starter lab |
| Kubernetes typos | `kubernetes_first_step_typos.md` | WEAK | honest learning start |
| Exam versioning | `quizey_exam_versioning.md` | STRONG | designed, not shipped |
| Attempt state machine | `quizey_attempt_state_machine.md` | STRONG | fix test-count |
| Idempotency | `quizey_idempotency.md` | STRONG | "harness"-level |
| DB is source of truth | `quizey_db_is_source_of_truth.md` | STRONG | open 2.1.4 gap |

## RED FLAG — `committed_ssh_key_to_git.md`

This is the **one story that must NOT be published as written.**

The story's central, headline claim is:

> "The private key file ended up tracked in the git repo. The repository had no
> `.gitignore`, so a real EC2 SSH private key was **committed**." (Problem), and the
> Evidence lists `/.../devops.pem` as "**the committed key**".

**Verified facts**:
- `devops.pem` exists in the working directory (size 1678, `-r--------`), and there
  is **no `.gitignore`** in the repo.
- **BUT `git ls-files` shows the ONLY tracked file is `math_utils.py`.**
- **Across all commits and all branches, `git log --all --name-only` returns NOTHING
  for `devops.pem`**. It was **never staged, never committed, never present in any
  commit**. A full check across `git rev-list --all` (all commit trees) found zero
  pem entries.

**Conclusion** — the key was in the working directory with no gitignore, but it was
**never actually committed to git history**. The story therefore **misleadingly
claims a commitment that did not happen**. As written it is **DO_NOT_USE / contradicted
by evidence**.

**The honest version** (if Alaa wants to keep any version of this story): the true, real,
defensible lesson is "a private key lived in the repo working tree with **no
`.gitignore`**, which is a real credential-hygiene hazard even though it was never
committed." That is supported by evidence. But it must **not** be described as "I
committed a key to git" — that specific claim is false for this repo.

Per the audit rules, since the story is **contradicted by evidence**, the correct action
is: **correct the story file to match the verified facts, or remove it**. Do not publish
the current version. (Flagged; rewriting is the owner's action, not invented.)

## Story Relationships

- Two DevOps CI stories (`ci_failures...` and `containerized_ci...`) both originate
  from the same `jenkins-practice` repo; they should point cross-reference; not be
  double-counted as two independent full projects. They are two angles of the same
  debugging journey.
- FastAPI layers and Quizey discipline have an explicit cross-project thread
  (Route→Service→Model); a single comparison piece works well.
- The four Quizey stories are four facets of **one** ongoing backend build. When used
  they must be mutually consistent (e.g., don't imply state machine AND versioning are
  both fully live/shipped). All currently claim design behavior in uncommitted work.
- evaluator_core stories (`never_trust_llm_arithmetic`, `dict_keys`, `fake_llm`,
  `build_mechanics` (the AI folder)) are one rounded "AI engineering" arc.

## Strongest 5 (by concrete, verifiable event + depth, NOT impressiveness)

1. `never_trust_llm_arithmetic.md` — exact, reproducible, hand-verifiable bug;
   reinforces the core "verify LLM with code" stance.
2. `ci_failures_are_environment_not_code.md` — first-hand multi-commit debugging with
   a root-cause and git-history trail.
3. `quizey_idempotency.md` — intentional design + proof (exactly-one-winner harness)
   for a real reliability concern.
4. `quizey_attempt_state_machine.md` — clean ORM-level domain design with verified
   transition map (after the test-count correct).
5. `build_mechanics_before_frameworks.md` — a deliberate engineering/learning choice
   with real artifacts (framed as a learning journey).

## Evidence Gaps / Weaknesses to Global Watch

- Quizey work sits in an **uncommitted** working tree (HEAD `bc8f7f5`). Fine as
  "designed", not as "shipped".
- `committed_ssh_key` must be corrected (see RED FLAG) or removed.
- `test_state_machine.py` actually collects 5 test cases, not the "24+" in the story.
- `build_mechanics` and `fastapi_layers` are lab/learning; never let them read as
  production in public posts.

## Stories That Should Not Be Published Yet

1. **`committed_ssh_key_to_git.md`** — as written (contradicted by git history).
   Needs correction or removal.
2. **`kubernetes_first_step_typos.md`** — honest start but no real result yet; not a
   public headline until there's a working cluster or a more progressed step.
3. FastAPI layers story — ok as a learning note, not a "production experience" claim.

## Next Actions

- [ ] Correct `committed_ssh_key_to_git.md` to the verified facts (untracked key +
      no gitignore, **not** committed to git) or remove it.
- [ ] Change the "24+" test-count to the verifiable "5 test cases / transition matrix".
- [ ] Make the "containerized CI fixed flakiness" claim explicitly about the harness/
      environment, and mark both CI stories as two angles of one journey.
- [ ] Apply the same layering/discipline honesty across the four Quizey stories
      (designed vs. shipped).
- [ ] Re-run this audit when Milestone 2.1.1 work is committed and the 2.1.4 gap
      is closed.