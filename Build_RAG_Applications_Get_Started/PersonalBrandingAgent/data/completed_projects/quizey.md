# Quizey — Flask quiz app (also labeled "Quizey V1")

## Status
Completed (collaboration: Alaa Badawy + Ali Gomaa). Remote origin:
`GitHub: AlaaBadawii/Quizey`.

> **Naming clarification (from the cross-source audit):** this project is
> presented on the portfolio as **"Quizey V1 — Exam Platform Backend System"**
> (`public_positioning/portfolio.md`, project card 3) and in the KB as
> **"Quizey"**. It is the SAME repository (`github.com/AlaaBadawii/Quizey`, a
> separate early ALX repo), not a distinct project. Use "Quizey V1" and
> "Quizey" interchangeably for this repo; the current rewrite is **Quizey V2**
> (a different, separate repo — see `../in_progress_projects/quizey_v2.md`).

> **NOTE: this is the OLD Quizey (a separate early ALX repo).** Alaa's **current
> active deep backend project is Quizey V2**, a production-oriented
> re-architecture (phases, state machine, RBAC, idempotency, audit). See
> `../in_progress_projects/quizey_v2.md`.

## What this is
A Flask-based quiz/exam backend API for teachers and students. Auth, email
verification, quiz/question-bank management, attempts, submission, and
auto-evaluation.

## Evidence of implemented
`/home/alaabadawii/ALX/Quizey/`
- `website/api/v1/routes/` — versioned routes: `auth.py`, `user.py`, `quiz.py`,
  `question.py`, `answer.py`, `bank.py`, `question_bank.py`, `quiz_attempt.py`,
  `analytics.py`.
- `website/models.py` — SQLAlchemy models (User, Quiz, Question, QuizAttempt,
  Answer, CorrectAnswer, QuestionBank).
- `website/oauth2.py` — bearer-token auth (JWT), `get_current_user()`.
- `website/oauth2.py`, `website/gmail_service.py` — Google OAuth Gmail sender for
  verification/reset emails.
- `website/utils.py` — `evaluate_quiz()` grading logic by question type, code
  generation utilities.
- `alembic/` — migration tooling (schema version `08539e121e83_crt_create_all_tables`).
- `endpoints_documentation.txt` — endpoint reference.

## Features implemented
- Registration, login, profile update/delete.
- Email verification + password reset.
- Teacher/student roles.
- Quiz CRUD + publishing; quiz types `mcq`, `mixed`, `written`.
- Question banks and question reuse.
- Attempts with submission and evaluation; attempt/participant limits;
  time-window availability.

## Explicitly NOT implemented (per repo README)
Shareable quiz links, leaderboards, and a fully built browser frontend page.
The app is an API, not a finished UI.

## Technologies
Flask, SQLAlchemy, PostgreSQL, Alembic, JWT/OAuth2 bearer tokens, Gmail API,
Python.

## Backend concepts practiced
- JWT-based auth and authorization checks (role ownership on resources, 401/403
  paths).
- Relational schemas with migrations.
- Async-ish outbound email via external API.
- Role-based access control (teacher vs student route behavior).

## Software engineering concepts practiced
Versioned API, route separation, migrations, endpoint documentation.

## Lessons supported
- Auth/authorization on real resources (ownership + role checks) is implemented,
  not just theory.
- Honest scoping: the README documents what is *not* done.

## Reported skill level (accurate, not inflated)
A functional, well-scoped backend API with real auth; frontend and advanced
features (leaderboards, sharing) intentionally not built.

## Evidence / key files
`/home/alaabadawii/ALX/Quizey/README.md`
`/home/alaabadawii/ALX/Quizey/website/api/v1/routes/`
`/home/alaabadawii/ALX/Quizey/website/oauth2.py`
`/home/alaabadawii/ALX/Quizey/website/utils.py`
`/home/alaabadawii/ALX/Quizey/alembic/versions/08539e121e83_crt_create_all_tables.py`
`/home/alaabadawii/ALX/Quizey/AUTHORS`