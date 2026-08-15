# Public Positioning — Personal Portfolio Site

## Source
`/home/alaabadawii/Portfolio/` — single-page site (`index.html` + `index.css`),
GitHub Pages remote `github.com/AlaaBadawii/AlaaBadawii.github.io`. Last
content commit `647babc` dated **2026-07-15** (before the Quizey V2 2.1.1
work, which happened after). Only images present are two favicon PNGs; the
three visible "photos" are **hot-linked external stock images** (Unsplash +
materevenue.com), not local assets. No resume PDF or README in the repo.

This file records what the portfolio *claims*, split into three buckets:
**Public positioning** (what he says), **Actual demonstrated experience**
(what the KB evidence in `../completed_projects/`, `../in_progress_projects/`
and `../stories_lessons/` supports), and **Claims requiring verification**
(assertions with no supporting evidence in either the portfolio repo or the KB).

---

## 1. Public positioning

### Professional identity (hero + footer)
- "Software Engineer" specialized in Python, RESTful APIs, and AI-powered
  backend systems — "building scalable platforms with Flask, SQLAlchemy, MySQL,
  and PostgreSQL, with hands-on experience designing autonomous AI agents."
  (index.html lines 45-47, 750)
- Based in Egypt (Cairo), title `<title>Software Engineer</title>`. Footer:
  "Software Engineer · Egypt". (lines 8, 742, 750)
- Nav logo monogram "AB". "Open to opportunities" hero tag.

### About me
- "Software Engineer based in Egypt, specialized in Python and RESTful API
  development... strong foundation in system design, database modeling, and
  clean architecture." (lines 99-101)
- "hands-on experience collaborating on team-based projects, improving
  existing codebases..." (lines 102-103)
- **Currently:** "interning in Backend AI Engineering at FlyRank, reviewing
  code hourly for Alignerr, and building Quizey — a production-style exam
  platform." (lines 104-106) — **FlyRank is UNVERIFIED** (see §C); the
  Alignerr phrasing overstates the conservative status (see §D).
- Stats: "6 Core Projects · 13 Certificates · 3+ Years Learning". (lines 107-119)

### Experience section
- Single card: **Alignerr** — Code Reviewer (Hourly). "Passed the interview and
  signed on as an hourly code reviewer roughly two weeks ago. Currently
  onboarded and waiting on my first review assignment — will share specifics
  once work begins." Status badge: "Onboarded · Awaiting first task". (lines
  132-144)
- **No FlyRank entry appears in the Experience section** — FlyRank is mentioned
  only in the About paragraph.

### Skills claimed
- Backend: Flask, REST APIs, MVC Architecture, JSON, HTTP, SQLAlchemy
- Languages & DBs: Python, C, MySQL, SQLite, PostgreSQL, MongoDB
- AI & Agentic: Agent Loops, Tool Calling, Multi-Agent Orchestration, Prompt
  Engineering
- Core: System Design, API Design, OOP, Data Modeling, Clean Architecture
- Tools: Git, GitHub, Postman, Docker, Linux, Bash
- Testing: Unit, Integration, API Testing, TDD
- Soft: Problem Solving, Analytical Thinking, Collaboration, Attention to
  Detail, Self-Learning
(lines 154-202)

### Projects presented publicly (6 cards, all with "In Progress / GitHub" badges)
1. **Quizey V2 — AI-Assisted Exam & Training Platform** — "Phase 1 complete:
   174 tests, production-grade architecture." **Note: "174 tests" is a STALE
   historical snapshot (site dated 2026-07-15); the authoritative current count
   is 254/255 (see `../in_progress_projects/quizey_v2.md` §Testing).** Badge:
   "In Progress · See case study below". Stack tags: AI, Docker, SQLAlchemy,
   Security, Flask — **"AI"/"Docker" tags overstate the repo's current state
   (see §J).** (lines 243-254)
2. **AI Agents From Scratch** — 3 agents (README agent, file assistant, multi-
   agent orchestrator), no frameworks. GitHub link. (lines 256-266)
3. **Quizey V1 — Exam Platform Backend System** — versioned REST API, token
   auth, email verification, password reset; PostgreSQL; Alembic. GitHub link.
   (lines 268-278)
4. **Taskey — Task Management System** — full-stack, auth, task lifecycle,
   priorities, deadlines, env-based DB config, theme persistence, profile
   uploads, modular Flask. (lines 280-290)
5. **Airbnb Clone — Backend System Foundation** — file+DB storage engines,
   RESTful APIs, Jinja2. (lines 292-302)
6. **Custom printf Implementation** — variadic functions, pointer arithmetic.
   (lines 304-314)

### Quizey V2 case study section (lines 318-402)
- Status numbers: **174 tests passing** (STALE historical snapshot; current =
  254/255 per `../in_progress_projects/quizey_v2.md`), "Phase 1 ✅ Complete",
  "3 phases ahead".
- Phase 1 described: "The core loop works end-to-end... Copy-on-write
  versioning keeps published exams immutable. JWT auth secures every endpoint.
  174 tests verify the entire system." — the "174 tests" figure is historical;
  the repo now reports 254 passing + 1 pre-existing structural failure.
- Phase 2 "Production Platform" marked **In progress — Next**.
- Phase 3 "AI-Native Learning" marked **Planned**.
- Phase 4 "Scale Architecture" (async/caching/event-driven) marked **Planned**
  — **not present in the repo roadmap** (repo = 3 phases; see §B).
- Philosophy: "build boring before building impressive."

### Values / approach (lines 205-236, 404-502)
- "Code Quality & Best Practices", PEP 8, modular/maintainable architecture,
  Flask Blueprints + app factory + MVC.
- "Collaboration & Communication", "Problem-Solving & Logical Thinking".

### Certificates / education (lines 504-621)
- Education: B.Sc. Management Information Systems, Modern Academy
  (10/2019–07/2023); ALX Software Engineering Program, Backend Specialization
  (09/2023–10/2024), "Completed".
- 9 featured certificates (7 "Completed" + 2 "In Progress"):
  ALX Professional Foundations (May 2026), Manara System Design (Mar 2026),
  Manara Node.js Backend (Apr 2026), Manara DevOps (Jun 2026), Vanderbilt AI
  Agents & Agentic Architecture in Python (Jul 2026), Vanderbilt AI Agents
  with Python & Generative AI (Jun 2026), AiCE (Apr 2026), Packt Practical
  DevOps Bootcamp (In Progress), IBM RAG and Agentic AI (In Progress).
- Additional: McKinsey Forward (Jul 2026), Speak English Professionally
  (Georgia Tech, Jun 2026), PyMongo — Advanced (EDUCBA, Jun 2026), Build with
  AI Masr (ITI & Google).
- "Currently growing": English for Tech Professionals (ASU), English grammar/
  pronunciation books, Never Split the Difference, "Up next: Cracking the
  Coding Interview".

### Vision / next 12 months (lines 623-670)
- Goal: grow from junior backend engineer into someone who can build, deploy,
  and scale AI-powered software platforms. Quizey should stop being a
  portfolio project and become a platform real teachers/schools/orgs use.
- Technical depth: async, system design, caching, cloud infra, Docker,
  Kubernetes. Career: secure a SWE role + start a Master's in Software
  Engineering. Communication: improve English. Community: document what he
  learns and build a personal brand "on real experience, not trends".

### Contact (lines 672-746)
- Phone +20 102 917 1634, email alaabadawii404@gmail.com, GitHub
  github.com/AlaaBadawii, "Egypt · Cairo".
- "Open to backend engineering roles, freelance projects, and collaborations.
  Always happy to discuss new opportunities... usually respond within 24 hours."
- Resume link: Google Drive folder (not a file in this repo).

### External links embedded in the page
- GitHub profile: https://github.com/AlaaBadawii
- Resume: https://drive.google.com/drive/folders/1svf-60hjMWKHx9_0TeOQ2A6fy18WGZ71
- AI Agents: https://github.com/AlaaBadawii/AI-Agents
- Quizey V1: https://github.com/AlaaBadawii/Quizey
- Taskey: https://github.com/AlaaBadawii/Taskey
- Airbnb Clone: https://github.com/AlaaBadawii/AirBnB_clone_v4
- printf: https://github.com/AlaaBadawii/printf

---

## 2. Actual demonstrated experience (KB-evidence-supported)

| Portfolio claim | KB evidence |
|---|---|
| Python/Flask/SQLAlchemy backend work | Supported by completed projects: Taskey, Quizey (old), Airbnb Clone, MongoDB CRUD; Quizey_V2 (in-progress) |
| MySQL, SQLite | Taskey, Airbnb Clone, Quizey_V2 (MySQL dev / SQLite test) |
| PostgreSQL + Alembic | Old Quizey (`quizey.md`: PostgreSQL, Alembic migrations) |
| JWT auth, email verification, password reset | Old Quizey KB confirms |
| Copy-on-write versioning on Quizey | Quizey_V2 `exam_service.py` + `00-summary.md` confirm |
| Auto-grading, attempts lifecycle | Quizey_V2 grading_service.py, attempt_service.py |
| AI agents from scratch (3 agents, no frameworks) | `ai_agents_from_scratch.md` (completed) confirms 3 framework-free agents |
| Team collaboration | Old Quizey (collab Alaa + Ali Gomaa), simple_shell (team project), Airbnb clone stages |
| "6 Core Projects" | The 6 project cards match 6 real repos, 4 of which are in the KB (Quizey old, Taskey, AI-Agents, AirBnB; printf maps to ALX C work; Quizey V2 = in-progress) |
| Docker, Linux, Bash, Git, Postman | DevOps KB files (docker_compose_flask_mysql_app, docker_nginx_packt_bootcamp, ci_cd_jenkins_github_actions) |
| MongoDB | `mongodb_pymongo_crud_service.md` confirms PyMongo work |
| Testing / TDD | Quizey_V2's authoritative 254-test suite (see `../in_progress_projects/quizey_v2.md` §Testing) + unittest/pytest practice |
| PEP 8, clean architecture, MVC, app factory, blueprints | Quizey_V2 architecture (Route→Service→Model), Taskey app factory |
| Certificates — the 13 listed in the portfolio | **NOT verified.** `certificates/` folder is EMPTY (no per-certificate evidence files yet), so these cannot be treated as verified until evidence exists; some have in-progress-course backing |
| AI/agentic interest + IBM course | `in_progress_courses/ibm_genai_llm_rag.md`, `evaluator_core.md`, `ai_agents_from_scratch.md` |
| Quizey as flagship / Phase 2 next | `quizey_v2.md` (KB) — matches, with important counter-points in §3 |
| "Open to opportunities", job-seeking | Consistent with `in_progress_projects/` and `vision_goals/` intent |

---

## 3. Claims requiring verification / contradictions

**A. Quizey V2 test count is OUT OF DATE.**
- Portfolio says "Phase 1 complete: **174 tests**" (lines 247, 326, 352, 356).
- Actual Quizey_V2 repo as of the latest run: **254 passing** tests (1
  pre-existing `test_structure.py` failure), and README documents 226. The
  "174" number is stale (pre-Phase-2-prerequisites) and the KB's
  `quizey_v2.md` records the real current count. **Contradiction (stale).**

**B. Portfolio phase roadmap does not match the repo's roadmap.**
- Portfolio shows a **4-phase** Quizey roadmap: Foundation / Production /
  AI-Native / Scale Architecture.
- The actual `docs/engineering/01-roadmap.md` and README describe a **3-phase**
  roadmap: Phase 1 Foundation / Phase 2 Production Platform / Phase 3
  AI-Native. There is no "Phase 4 — Scale Architecture" in the repo. Also the
  portfolio's "3 phases ahead" implies a count that doesn't align with repo
  docs (repo Phase 2 has 7 stages; "3 phases ahead" is ambiguous).
  **Contradiction (portfolio is looser than the repo).**

**C. "Interning in Backend AI Engineering at FlyRank" (About, line 104) — MARKED
UNVERIFIED.**
- The Experience section lists only Alignerr; no FlyRank entry appears there.
- No FlyRank evidence exists in the portfolio repo, the KB, or the Quizey_V2
  workspace. **UNVERIFIED — do not repeat as fact until evidence is provided.**

**D. Alignerr claim — keep the CONSERVATIVE interpretation.**
- About says "reviewing code hourly for Alignerr" (line 104); the Experience
  card explicitly says "onboarded · awaiting first task" and "will share
  specifics once work begins" (lines 141-144). These two statements are in
  tension: "reviewing code hourly" reads as active work, while the Experience
  card says no review work has started yet. **Adopted interpretation: treat the
  role as SIGNED-ON / ONBOARDED and awaiting first task — NOT active review
  work — until the Experience card post-states otherwise.**

**E. "13 Certificates" stat is unverifiable from inside the portfolio.**
- The page lists 7 completed + 2 in-progress featured certificates + 4
  "additional" pills = 13 total items, so the number is internally plausible —
  but the KB `certificates/` folder is empty (no per-certificate evidence
  files yet), and no certificate files/images exist in the Portfolio repo
  (only favicons). **Claims require verification (need actual certs).**

**F. "3+ Years Learning" is a soft, unverifiable stat** (no timeline evidence
in the repo; git history begins 2024-06, education spans 2019–2024). **Soft claim.**

**G. Photos are not local/real.** The About "Developer workspace photo" and the
two Approach photos are hot-linked stock images (Unsplash, materevenue.com),
not personal photos; the local `images/` folder contains only favicons. The
"developer workspace photo" aria-label does not match the actual stock content
(business-team image). **Presentation nuance, not a factual skill claim.**

**H. Resume link is an external Google Drive folder, not a file in the repo**
— no resume PDF to inspect; the "Get Resume" CTA cannot be verified from here.

**I. Skill claims with thin/absent evidence in the KB:**
- **PostgreSQL** — only via old Quizey KB (postgres) and the portfolio's own
  claim; Quizey_V2 uses MySQL. Partially evidenced.
- **MongoDB** — supported by the PyMongo CRUD service + "PyMongo — Advanced"
  cert claim. OK but basic.
- **Kubernetes** — listed only in the *vision* (future), not in skills; but
  `kubernetes_manara_lab.md` shows early-stage minikube work. Fine.
- **"System Design", "API Design", "Clean Architecture", "TDD"** — these are
  portfolio-level competency claims; some support exists (Quizey_V2 docs,
  Manara System Design cert claim) but depth is not proven by the portfolio
  itself. **Competency claims.**

**J. Project-stack tag mismatches — required correction:**
- Quizey V2 card lists **"Docker"** and **"AI"** tags. Docker: no Docker
  evidence in Quizey_V2 repo (no Dockerfile/compose found in the workspace
  tree — resolved authoritative evidence); "AI": Phase 3 is planned only,
  nothing AI is implemented yet; the repo Phase 2 is deliberately AI-free
  (00-overview.md). **These tags overstate the repo's current state and
  should be removed/corrected in any future site edit.** Note: a *separate*
  FastAPI project and other Docker work exist elsewhere in the KB, but they are
  not part of the Quizey V2 repo infrastructure.
- printf project is presented as its own project; it's an ALX curriculum
  exercise (matches `simple_shell`/ALX C context). Not a contradiction, just
  provenance.

**K. The "about-photo" / approach photos being stock** (see G) also means the
site visually implies a personal workspace/team photo that isn't real. Minor.

**L. Alignerr "roughly two weeks ago" (from 2026-07-15) + "awaiting first task"
— no evidence of actual code review activity anywhere in the KB or repos.**
So the resume/portfolio claim "Code Reviewer" is a *signed/onboarded* role,
not demonstrated review work. **Consistent with the adopted conservative
reading (§D): signed-on and awaiting first task. Framing as active experience
would overstate it.**

---

## 4. Cross-checks vs. this KB (alignment notes)
- The portfolio and the KB agree on: Python/Flask/backend focus, AI-agents
  interest, Quizey as flagship, IBM RAG + Packt DevOps as in-progress courses,
  Alignerr role (portfolio) / job-seeking intent.
- The portfolio is **more optimistic** than the KB in: Quizey test count (174
  — marked stale vs the authoritative 254/255), FlyRank internship (UNVERIFIED),
  phase count (4 vs 3), the Quizey "Docker/AI" stack tags (flagged for
  correction), and the 13 certificates (NOT verified — evidence gap).
- The KB's `quizey_v2.md` is the authoritative current record for Quizey V2;
  the portfolio's Quizey case study is dated 2026-07-15 and predates the
  Phase-2-prerequisites + 2.1.1 work.

## 5. Notes for honest storytelling (do NOT turn into posts here)
- The strongest, evidence-backed narrative threads are the ones already
  captured in `completed_projects/`, `in_progress_projects/`, and
  `stories_lessons/`. Any future post should avoid repeating the stale "174
  tests" figure (use 254/255), the unverified FlyRank claim, and the
  unverified 13-certificates count.

## Provenance
- `/home/alaabadawii/Portfolio/index.html` (single source for all quotes)
- `/home/alaabadawii/Portfolio/index.css` (photo URLs, lines 331/520/526)
- `/home/alaabadawii/Portfolio/images/` (only favicons)
- `/home/alaabadawii/Portfolio/.git` — git history (20 commits, 2024-06-01 →
  2026-07-15), remote `AlaaBadawii/AlaaBadawii.github.io`
- KB cross-references: `../completed_projects/quizey.md`,
  `../completed_projects/taskey.md`, `../completed_projects/ai_agents_from_scratch.md`,
  `../completed_projects/airbnb_clone.md`, `../in_progress_projects/quizey_v2.md`,
  `../in_progress_projects/evaluator_core.md`,
  `../in_progress_courses/ibm_genai_llm_rag.md`, `../in_progress_courses/devops_manara_packt.md`
