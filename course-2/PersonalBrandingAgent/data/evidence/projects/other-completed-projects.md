# Other Completed Projects — Evidence

Aggregate evidence for the remaining completed projects in the KB. Each entry
lists what was actually built (evidence-backed). Primary sources:
`../completed_projects/*`.

---

## Taskey — Flask task management app

- **Evidence state:** VERIFIED (completed repo `github.com/AlaaBadawii/taskey`).
- **What was built:** Flask app factory; session auth (Flask-Login) with
  signup/login/logout/account deletion; task CRUD with groups, due dates,
  priorities, checklists; per-user dark theme; profile picture upload; SQLite
  fallback + optional MySQL via `DATABASE_URL`; Locust load-test script.
- **Technologies demonstrated:** Flask, Flask-Login, Flask-SQLAlchemy, Jinja2,
  MySQL/SQLite, Locust.
- **Publicly safe claim:** "I built a full-stack task management app in Flask
  with user accounts, task lifecycle, and a configurable database."
- **Evidence source:** `../completed_projects/taskey.md`, `/home/alaabadawii/ALX/taskey/`.

---

## AirBnB Clone (HBnB) — multi-stage full-stack project

- **Evidence state:** VERIFIED (ALX multi-stage repo).
- **What was built:** Stage 1 console + JSON FileStorage; Stage 2 Flask + MySQL /
  SQLAlchemy; Stage 3 RESTful API; Stage 4 API docs + dynamic frontend (Jinja2).
  File + DB storage engines, RESTful APIs.
- **Technologies demonstrated:** Python, Flask, SQLAlchemy, MySQL, REST, Jinja2.
- **Publicly safe claim:** "I built a multi-stage AirBnB clone backend across
  console → Flask/MySQL → RESTful API stages during the ALX program."
- **Evidence source:** `../completed_projects/airbnb_clone.md`.

---

## Files Manager — Node.js/Express file management API (ALX)

- **Evidence state:** VERIFIED (completed ALX project).
- **What was built:** Node/Express API using MongoDB, Redis and Bull (queue).
- **Technologies demonstrated:** Node.js, Express, MongoDB, Redis, Bull.
- **Publicly safe claim:** "I built a Node.js/Express file-management API with
  MongoDB, Redis, and a background job queue as part of ALX."
- **Evidence source:** `../completed_projects/files_manager.md`.

---

## simple_shell — custom Unix shell in C (ALX)

- **Evidence state:** VERIFIED (ALX low-level project).
- **What was built:** A custom Unix shell in C (ALX two-person team project).
- **Publicly safe claim:** "I built a Unix shell in C as an ALX team project."
- **Evidence source:** `../completed_projects/simple_shell.md`.

---

## GenAI Flask App — LangChain playground (IBM course rebuild)

- **Evidence state:** VERIFIED (implemented locally).
- **What was built:** Flask app; LCEL chain `ChatPromptTemplate → ChatOpenAI
  (OpenRouter) → JsonOutputParser`; structured JSON (summary + sentiment +
  suggested reply) validated via Pydantic; 3-model selection; documented decision
  to replace per-model watsonx templates with one shared chat-completions
  template.
- **Technologies demonstrated:** Python, Flask, LangChain LCEL, Pydantic,
  OpenRouter.
- **Capability shown:** hands-on use of LCEL, structured output, Pydantic
  validation, provider abstraction. Local/experimental, not deployed.
- **Publicly safe claim:** "I built a small Flask app that returns
  schema-validated LLM output, using LangChain LCEL and a provider abstraction."
- **Evidence source:** `../completed_projects/genai_flask_app.md`,
  `/home/alaabadawii/LLMs/IBM/course-1/GenAI_Flask_App/`.

---

## Book/Movie Advisor — mood-based recommender (IBM)

- **Evidence state:** VERIFIED (implemented locally; course-completed practice).
- **What was built:** Mood-based recommendation app applying the IBM course
  concepts.
- **Publicly safe claim:** modest, at the same "built a small LLM app" level as
  the GenAI Flask App.
- **Evidence source:** `../completed_projects/book_movie_advisor.md`.

---

## ALX curriculum (broad) — `../completed_projects/alx_backend_engineering.md`

- Evidence state: VERIFIED (completed ALX tracks).
- Covers backend fundamentals, JavaScript/Node track, advanced Python, storage
  (MySQL/MongoDB/Redis study), user data & auth, DevOps/SysAdmin.
- These are **coursework evidence**, not independent production experience.
