# Quizey V1 — Evidence (old ALX repo)

Distinct from Quizey V2. This is the OLD Quizey, also presented on the portfolio
as **"Quizey V1 — Exam Platform Backend System"** — the SAME repository
(`github.com/AlaaBadawii/Quizey`), not a separate project. Source:
`../completed_projects/quizey.md`, repo `/home/alaabadawii/ALX/Quizey/`.

## Evidence state

VERIFIED (completed repo with implementation files).

## What was actually built (evidence-backed)

- Flask backend API with versioned routes under `website/api/v1/routes/`
  (`auth.py`, `user.py`, `quiz.py`, `question.py`, `answer.py`, `bank.py`,
  `question_bank.py`, `quiz_attempt.py`, `analytics.py`).
- SQLAlchemy models (User, Quiz, Question, QuizAttempt, Answer, CorrectAnswer,
  QuestionBank).
- JWT/OAuth2 bearer auth (`oauth2.py`, `get_current_user()`), role checks on
  resources.
- Email verification + password reset via Google OAuth Gmail sender
  (`gmail_service.py`).
- Grading logic `evaluate_quiz()` by question type; quiz types `mcq`, `mixed`,
  `written`; question banks/reuse; attempts with submission/evaluation,
  attempt/participant limits, time-window availability.
- Alembic migrations (schema version `08539e121e83_crt_create_all_tables`).
- Endpoint documentation file.
- Collaboration: Alaa Badawy + Ali Gomaa.

## What was NOT built (per repo README — honest scope)

Shareable quiz links, leaderboards, a fully built browser frontend. The app is an
API, not a finished UI.

## Technologies demonstrated

Flask, SQLAlchemy, PostgreSQL, Alembic, JWT/OAuth2, Gmail API, Python.

## Publicly safe claim

- "I built a Flask quiz/exam backend API with JWT auth, email verification,
  password reset, question banks, and auto-evaluation, as part of the ALX
  program (collaborating with a teammate)."

## Claims requiring caution

- Do not conflate with Quizey V2 (separate, current rewrite).
- Frontend/leaderboards were explicitly not built — do not claim them.

## Related

- Quizey V2 (`projects/quizey_v2.md`) — the current production-oriented rewrite.

## Evidence source

`../completed_projects/quizey.md`, `/home/alaabadawii/ALX/Quizey/README.md`,
`website/api/v1/routes/`, `website/models.py`, `website/oauth2.py`,
`website/utils.py`, `alembic/versions/08539e121e83_crt_create_all_tables.py`,
`AUTHORS`.