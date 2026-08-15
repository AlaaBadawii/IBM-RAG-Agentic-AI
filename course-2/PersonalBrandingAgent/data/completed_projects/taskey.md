# Taskey — Flask task management app

## Status
Completed (solo project). Remote origin: `GitHub: AlaaBadawii/taskey`.

## What this is
A full-stack task management web app with user accounts, groups, priorities,
due dates, multi-step checklists, theme settings, and profile photos.

## Evidence of implemented
`/home/alaabadawii/ALX/taskey/`
- `app.py` (Flask app factory), `auth.py` (signup/login/logout/account deletion),
  `main.py` (dashboard, create/edit/complete/delete tasks, Today/Upcoming/Group
  views, settings).
- `models/` — `basemodel.py`, `user.py`, `task.py`, `group.py`, `tag.py`
  (Flask-SQLAlchemy).
- `utils/` — `tasks.py` (step serialization/summary building), `files.py`
  (profile image save/delete), `dates.py` (due-date parsing).
- `templates/` + `static/` — Jinja2 UI, dark-mode, responsive CSS.
- `locustfile.py` — Locust load-testing script against the app.

## Features implemented
- Signup/login/logout/account deletion; password change.
- Task CRUD with groups, due dates, priorities, descriptions, checklists.
- Task counts (total/completed/pending).
- Per-user theme (dark mode) and profile picture upload.
- Automatic table creation; SQLite fallback + optional MySQL (`DATABASE_URL`).

## Technologies
Flask, Flask-Login, Flask-SQLAlchemy, SQLAlchemy, Jinja2, vanilla JavaScript,
MySQL or SQLite, Locust.

## Backend concepts practiced
- Session-based auth (Flask-Login).
- ORM modeling with relationships and per-user scoping.
- Dynamic form handling and validation.
- File upload handling and safe removal on account deletion.
- Configurable database backend (SQLite dev vs MySQL).

## Software engineering concepts practiced
Application factory pattern, blueprint separation (auth vs main), utility module
separation, load testing with Locust.

## Lessons supported
- A usable end-to-end CRUD web app with real auth and persistence was shipped.
- Configuration-driven database selection keeps dev simple.

## Reported skill level (accurate, not inflated)
Solid course-level full-stack Flask app. Vanilla JS/CSS rather than a frontend
framework. No test suite found in the repo (beyond the Locust load script).

## Evidence / key files
`/home/alaabadawii/ALX/taskey/README.md`
`/home/alaabadawii/ALX/taskey/app.py`
`/home/alaabadawii/ALX/taskey/main.py`
`/home/alaabadawii/ALX/taskey/models/`
`/home/alaabadawii/ALX/taskey/locustfile.py`