# Source Registry

## Purpose

This document records **what the Personal Branding Agent is allowed to treat as
evidence about its user**, and the inspection that established it.

It exists because the instruction that produced the registry was *do not invent
source paths from labels* — "IBM", "Quizey", "FastAPI", "DevOps" are names in a
roadmap, not directories on a disk. Every path below was checked against the
filesystem, and every claim about a repository (commit count, authorship,
remote) was read from git rather than inferred from a document.

The registry itself is [`sources.yaml`](../../sources.yaml) at the project root.
This document is why it says what it says.

---

## The problem: workspace roots are places to look, not sources

`PLAN.md` §5.3 declares eight workspace roots. Treated as *sources*, they would
put into the knowledge base:

```text
~28 git repositories across two training programs and several personal projects
17 Python virtual environments, ~17 GB of third-party library code
third-party course templates the user did not write
a cohort's shared repositories where 1 of 235 commits is the user's
this application's own source, planning documents, and runtime state
```

The last entry is the sharpest. `~/LLMs/IBM` is a git repository that
**contains this application**, so it is both an unavoidable source and, without
an explicit exclusion, a source that ingests `PLAN.md`, `app/`, `chroma_db/`,
`logs/`, `state_db/`, and the LinkedIn token file as professional evidence.

So: roots are inspected and never ingested. The registry names 29 exact sources,
and no code anywhere scans a root to discover sources.

---

## Inspection method

For every directory under every declared root, at full depth:

| Question | How it was answered |
|---|---|
| Is it a repository? | presence of `.git/`, plus `git -C <path> rev-list --count HEAD` |
| Which repository? | `git remote get-url origin`, then sanitized (see *Credentials*) |
| Whose work is it? | `git shortlog -sn HEAD` — authorship, aggregated across the user's several git identities |
| What is in it? | a per-directory extension census run **through the registry's own matcher**, so excludes were proven rather than assumed |
| Is it a virtualenv? | presence of `pyvenv.cfg` — structural, not name-based |

The extension census matters more than it sounds. A plain `find` reported 36,082
`.py` files under `~/LLMs/IBM`; the same walk through the actual include/exclude
rules reports **93**. That gap is the entire difference between a knowledge base
about a person and a copy of `site-packages`.

---

## Findings: the declared roots

| Root | Kind | What is actually there |
|---|---|---|
| `~/LLMs/IBM` | git, 16 commits | **Monorepo containing this application** + 5 course project directories. `PLAN.md` §5.3 records 13 commits; the real count is 16. |
| `~/LLMs/AI_Agents` | git, 12 commits | 4 subprojects, 2 with their own virtualenvs |
| `~/LLMs/AI_Hackthon` | plain directory | 1 nested repo (18 commits) + 1 lab that is not a repo at all |
| `~/Quizey` | plain directory | `Quizey_V2` (git, 27) + `Quizey_Platform` (git, 3) |
| `~/FastAPI` | plain directory | a repo with **zero commits**, a directory of course code, and a 164 MB virtualenv |
| `~/DevOps` | plain directory | 3 nested repos + `Manara/Kubernetes_lab`, a plain directory |
| `~/ALX` | plain directory | **20 nested repositories** — 2 training programs' coursework |
| `~/Portfolio` | git, 21 commits | static site, published from this repository |
| `~/DataBases` | plain directory | **not in `PLAN.md` §5.3** — found by following the corpus's own source references |

`~/DataBases` was added to the roots because the corpus claims MongoDB/PyMongo
work and cites a path outside every root the roadmap declares. A registry that
only looked where the roadmap said to look would have silently dropped a source
the knowledge base already believed in.

---

## Findings: sources

`c` = commit count. Classification is one of *professional project*,
*coursework*, or *public artifact*.

### Applications and public artifacts

| Name | Path | Type | c | Content | Class | Lifecycle |
|---|---|---|---|---|---|---|
| `ibm-genai-coursework` | `~/LLMs/IBM` | git | 16 | Python, notebooks, JS/HTML | coursework + this app | ACTIVE |
| `ai-agents` | `~/LLMs/AI_Agents` | git | 12 | Python agents | professional project | ACTIVE |
| `quizey-v2` | `~/Quizey/Quizey_V2` | git | 27 | Flask/Python, 128 `.py` | professional project | ACTIVE |
| `quizey-platform` | `~/Quizey/Quizey_Platform` | git | 3 | README only | public artifact | ACTIVE |
| `fastapi-shipment-api` | `~/FastAPI/course_practical_app` | filesystem | — | 20 `.py` | professional project | ACTIVE |
| `exit-project-studyflow` | `~/FastAPI/ExitProject` | git | **0** | 11 planning docs + scaffold | professional project | PLANNED |
| `portfolio` | `~/Portfolio` | git | 21 | HTML/CSS/JS | public artifact | ACTIVE |
| `kubernetes-lab` | `~/DevOps/Manara/Kubernetes_lab` | filesystem | — | YAML manifests + notes | coursework | ACTIVE |
| `devops-lab` | `~/DevOps/Manara/devops-lap` | git | 1 | Docker/YAML/Python | coursework | ACTIVE |
| `databases-mongodb-crud` | `~/DataBases/MongoDB` | filesystem | — | PyMongo scripts | coursework | COMPLETED |

### Coursework repositories

| Name | Path (under `~/ALX/`) | c | Content |
|---|---|---|---|
| `alx-airbnb-clone-v1` | `AirBnB_clone` | 48 | all 48 commits the user's; console/object model |
| `alx-airbnb-clone-v2` | `AirBnB_clone_v2` | 150 | 55 the user's; Flask + SQLAlchemy web layer |
| `alx-backend` | `alx-backend` | 39 | backend fundamentals |
| `alx-backend-javascript` | `alx-backend-javascript` | 96 | 146 `.js` |
| `alx-backend-python` | `alx-backend-python` | 53 | advanced Python |
| `alx-backend-storage` | `alx-backend-storage` | 46 | 16 `.sql`, MySQL/NoSQL |
| `alx-backend-user-data` | `alx-backend-user-data` | 144 | auth, personal data |
| `alx-system-engineering-devops` | `alx-system_engineering-devops` | 258 | **127 extensionless shell scripts** |
| `alx-files-manager` | `alx-files_manager` | 2 | Node/Redis/MongoDB |
| `alx-higher-level-programming` | `alx-higher_level_programming` | 274 | Python + JS + C |
| `alx-interview` | `alx-interview` | 33 | algorithm practice |
| `alx-program-revision` | `alx_program_Revision` | 10 | largest source (~1,600 files) |
| `alx-simple-shell` | `simple_shell` | 101 | **a C program**; 53 commits the user's, remote belongs to a teammate |
| `alx-taskey` | `taskey` | 28 | Flask task API |
| `alx-quizey` | `Quizey` | 84 | Quizey V1 — **a different repository from `quizey-v2`** |
| `hackathon-lectures` | `~/LLMs/AI_Hackthon/hackathon_lectures` | 18 | lecture material |
| `hackathon-practice-lab` | `~/LLMs/AI_Hackthon/hackathon_practice_lab` | — | not a repo |
| `jenkins-practice` | `~/DevOps/jenkins-practice` | 14 | CI practice |
| `kodekloud-devops-specialization` | `~/DevOps/KodeKloud_devops_pro_specialization` | 6 | shell + Markdown |

Two findings shaped the include model:

- **`alx-system-engineering-devops` has 127 extensionless files.** ALX names its
  shell scripts `0-hello_world`, `101-metadata`. No extension-based pattern can
  reach them, so this source uses a broad profile with explicit binary
  exclusions instead.
- **`alx-simple-shell` is C**, and `alx-backend-storage` is SQL. A single
  Python-shaped include list would have admitted almost nothing from either.

---

## Findings: considered and deliberately not registered

Recorded in `sources.yaml` under `not_registered`, so "we decided against this"
stays distinguishable from "we never noticed it". The evidence:

| Path | Why not |
|---|---|
| `~/ALX/AirBnB_clone_v4` | The **cohort's** repository. 1 of 235 commits is the user's (alexaorrico 90, jzamora5 57). The corpus's `portfolio.md` links to it as the user's AirBnB project. |
| `~/ALX/AirBnB_clone_v3` | Cohort shared: 17 of 147 the user's. |
| `~/ALX/_AirBnB_clone_v2` | Duplicate working copy (34 of 129); referenced by nothing in the corpus. |
| `~/ALX/AirBnB_clone_the_console` | 2-commit stub, superseded by `alx-airbnb-clone-v1`. |
| `~/ALX/instance` | Flask instance dir holding `taskey.db` — runtime state. |
| `~/ALX/snap` | Snap package install tree. |
| `~/FastAPI/fastapi_venv` | 164 MB virtualenv. |
| `~/LLMs/IBM/…/Style_Finder` | **IBM's course template.** 3 commits by Enaya Amir (IBM), 1 by `ibm-skills-network-bot`, 0 by the user. |
| `~/DSA-Python-LeetCode-130` | 7 commits of DSA practice; outside every declared root. Registering it would mean the registry quietly widening what it reads. |
| `~/Cline` | Agent-tooling configuration. |

**`Style_Finder` is the important one.** It is a git repository nested inside
the IBM monorepo, and it is the kind of thing that gets ingested by accident:
it looks like the user's project because it sits in the user's directory. Its
four commits belong to IBM.

---

## Cross-cutting findings

### Credentials embedded in git remotes

**14 repositories carry a live token in their local git remote URL**, e.g.

```text
https://AlaaBadawii:ghp_…@github.com/AlaaBadawii/taskey
```

This makes the sanitizer a requirement rather than a precaution: `repo_identity`
is written into a **committed** file, and copying a remote verbatim would publish
a token. `sanitize_repo_url()` strips URL userinfo, `looks_like_credential()`
refuses known token shapes, and registry validation fails the load if either is
violated. No token value appears in `sources.yaml`.

### Virtual environments are not uniformly named

17 virtual environments, ~17 GB, under names `.venv`, `venv`, `my_env`, and
`fastapi_venv`. Name-based exclusion is therefore unreliable, so detection is
**structural** (`pyvenv.cfg`), the conventional names are excluded universally,
and validation refuses to load a registry that leaves any virtualenv admissible
inside a source.

### Nested repositories

Repositories nested inside sources were found in both directions — a repo inside
a plain directory (`~/DevOps/Manara/devops-lap`), and a plain directory holding
repos (`~/Quizey`). A nested repository is never absorbed silently: it must be
registered in its own right or excluded with a reason, or the load fails. The
scan is breadth-first with a hard depth cap, and hitting that cap is a
**failure, not a truncation**, because a scan that stopped early has proved
nothing.

### Corpus path drift, confirmed

| Recorded in the corpus | Reality |
|---|---|
| `~/LLMs/AI-Agents` | `~/LLMs/AI_Agents` |
| `~/Quizey_V2` | `~/Quizey/Quizey_V2` |
| `~/LLMs/IBM/course-1`, `course-2` | renamed to the long course names |
| `~/FastAPI/app` | `~/FastAPI/course_practical_app` |
| `~/DevOps/Packt-DevOps-Bootcamp` | gone |
| `~/LLMs/llm-env` | gone |

The registry is what makes this drift visible instead of load-bearing.

---

## Registry format

```yaml
version: 1
include_profiles:   # named pattern sets, referenced by YAML alias
defaults:           # exclusions inherited by every source
workspace_roots:    # places to inspect — never sources
sources:            # the registry proper
not_registered:     # considered and deliberately excluded, with evidence
```

### Per-source fields

| Field | Meaning |
|---|---|
| `name` | stable identifier, unique across the registry |
| `type` | `git` or `filesystem` |
| `local_path` | absolute path; must exist |
| `repo_identity` | git only — remote or stated absence, **sanitized** |
| `ref` | git only — the ref synchronization tracks |
| `lifecycle` | `ACTIVE` · `PAUSED` · `COMPLETED` · `PLANNED` |
| `include` | patterns that admit; an empty list admits nothing |
| `exclude` | patterns that reject, **each with a reason** |
| `description` | what this source is, and anything a reader must know |

`sync_state` — the last processed revision and timestamp — is deliberately
**not** a field here. It is runtime state and lives in the Step 1 store's
`sync_checkpoints` table.

### Matching grammar

gitignore-shaped, and deliberately small:

- `*` matches within a path segment, `**` across segments, `?` one character.
- A pattern containing no `/` matches at any depth (`notes.md`).
- A **trailing `/` marks a directory pattern** and matches everything beneath
  it (`**/venv/` reaches `a/venv/lib/mod.py`).
- Matching respects path-component boundaries: `Agent/` does not match
  `AgentX/`.
- **Include is a floor, exclude is a veto, and the veto always wins.** A path is
  admitted only if some include pattern matches it *and* no exclude pattern
  does. Deny-wins rather than last-rule-wins, so the outcome depends on which
  rules exist rather than on the order someone happened to write them in.
- Character classes (`[abc]`) are **rejected**, not approximated: silently
  treating one as a literal would create an exclusion that excludes nothing, and
  nothing downstream would report it.

### Include profiles

Three named sets, referenced by alias. Deliberately few: tailoring one per
language would add ceremony without changing what is admitted, because a stray
`.js` in a Python repository is still the user's work. What must *not* be
admitted is the exclusions' job.

| Profile | Contents |
|---|---|
| `source_code` | authored text and configuration across languages (`.py`, `.c`, `.js`, `.md`, `.sql`, `.yml`, … plus extensionless `Dockerfile`/`Jenkinsfile`/`Makefile`) |
| `docs_only` | `.md`, `.txt` — for a source that is a written statement and nothing else |
| `shell_repo` | everything, for the ALX shell repositories whose scripts have no extension |

### Validation at load time

Every entry is checked before synchronization may run, and **every problem is
reported at once** rather than one per attempt:

```text
path exists · type matches reality (a git source has a repository;
a filesystem source does not) · names are unique · patterns are well-formed
· every exclusion states a reason · no source is a plain declared root
· no git source is missing repo_identity/ref · a filesystem source carries neither
· nothing in not_registered is also registered
· nested repositories are registered or excluded
· no virtualenv is left admissible inside a source
· no source would admit a protected path inside the application
· no repo_identity contains a credential
```

A registry that fails any of these **refuses to run**. A partial registry that
silently drops a source is worse than no run at all: the missing source produces
no error, no signal, and a knowledge base that quietly stops covering part of
the user's work.

---

## The self-ingestion guard

Two layers, because either alone leaves a hole.

**Structural** — `is_protected(path)` answers for a single path and consults no
registry at all. It resolves symlinks first, so a link that merely *looks* like
it points elsewhere cannot launder access.

**Validated** — the registry is checked at load time against a list of concrete
protected probe paths (`.env`, `Auth_handling/linkedin_tokens.json`,
`chroma_db/chroma.sqlite3`, `state_db/operational_state.db`, `app/`, `PLAN.md`,
`sources.yaml`, `data/…`). If any source's patterns would admit one, the load
fails with the offending pattern named.

`data/` is in that probe list on purpose: the corpus is a *digest* of the
sources, so re-ingesting it would make the knowledge base its own evidence.

---

## Lifecycle

`ACTIVE` · `PAUSED` · `COMPLETED` · `PLANNED` — declared, stored, and **never
inferred from inactivity** or from a Markdown heading.

Lifecycle governs **depth and priority, never visibility**:

| Lifecycle | Disposition | Priority |
|---|---|---|
| `ACTIVE` | ingest quietly | HIGH |
| `COMPLETED` | ingest **and** raise a status-review signal | LOW |
| `PAUSED` | ingest **and** raise a status-review signal | LOW |
| `PLANNED` | ingest **and** raise a status-review signal | LOW |

`COMPLETED` must never mean `IGNORE FOREVER`. A finished project receiving
commits is the single most informative event the synchronizer can see, so it is
ingested in full and additionally surfaces as `REQUIRES_HUMAN_INTERVENTION`,
asking whether the project is finished after all or the declaration is stale.

The type makes the forbidden outcome unrepresentable rather than discouraged:
`SyncDisposition` has no `skip` member, and every plan carries `ingest=True`.
A source with **no changes** always takes `NORMAL` — firing a signal for an
unchanged repository would train the user to ignore signals, and a review gate
nobody reads is not a gate.

---

## Definition vs. state

| | Where | Committed |
|---|---|---|
| Which sources exist, and what they admit | `sources.yaml` | yes |
| Last processed revision, lifecycle transitions | `state_db/` (`sync_checkpoints`, `source_lifecycle`) | no |

Writing a revision into `sources.yaml` would make committed configuration churn
on every run. The two are kept apart by construction.

---

## What this step does not do

- **No git incremental synchronization.** The registry declares `ref`; deciding
  *what changed since the last revision* is Step 3.
- **No ingestion changes.** `app/ingestion/` and `app/retrieval/` are untouched.
- **No `data/` restructuring.**
- **No lifecycle transitions.** The store has the table; recording a transition
  belongs to Step 3.

One deliberate nuance in the "a root is never a source" rule, which the
workspace forced: **a git repository rooted at a declared root is one source**,
because one revision history is exactly what a source is. `~/LLMs/IBM`,
`~/LLMs/AI_Agents`, and `~/Portfolio` are all both. The rule the validation
enforces is therefore that a *filesystem* source may never be a declared root —
a plain directory taken wholesale is the hazard, and a git source that is not
really a repository is caught by a separate check.
