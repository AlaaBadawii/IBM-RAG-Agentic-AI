# Manara DevOps Lab — Flask + MySQL containerized with Docker Compose

## Status
COMPLETED (built, local). Source:
`/home/alaabadawii/DevOps/Manara/devops-lap/` (git repo, branch `main`,
single commit "Initial Flask application with tests"). Part of the Manara
DevOps learning track.

## What this is
A small Flask app wired to a MySQL database, both running as containers via
Docker Compose. Exercises local Dockerization and multi-container orchestration.

## Evidence of built work
- `Dockerfile` — `python:3.10`, app at `/app`, `pip install -r requirements.txt`,
  `EXPOSE 5000`, `CMD python app/app.py`.
- `docker-compose.yml` — two services:
  - `db`: `mysql:8`, named volume `mysql_data:/var/lib/mysql`, port 3306,
    env-driven credentials (`MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`).
  - `web`: `build: .`, port 5000, `depends_on: db`, env config
    (`DB_HOST/DB_USER/DB_PASSWORD/DB_NAME`), `restart: always`.
- `app/app.py` — Flask + Flask-SQLAlchemy/PyMySQL; `/`, `/health`,
  `/db-test` (live DB connectivity probe).
- `tests/test_app.py` — pytest for `/` and `/health`.
- `.dockerignore`.

## Tools & concepts
Docker, Docker Compose (multi-service, `depends_on`, named volumes for state),
MySQL 8, SQLAlchemy/pymysql, environment-driven config, pytest, health checks.

## Lessons supported
- Environment-variable-driven DB config keeps a containerized app deployable
  without code changes.
- `docker-compose` `depends_on` + named volumes model a real db + app topology.

## Accurate classification
BUILT (local, first-stage). Compose `depends_on` here does not wait for MySQL
to be healthy (no `healthcheck` on `db`), so first runs can race — a typical
beginner gap. Docker knowledge is at a working lab level, not production
orchestration.

## Provenance
`/home/alaabadawii/DevOps/Manara/devops-lap/docker-compose.yml`
`/home/alaabadawii/DevOps/Manara/devops-lap/Dockerfile`
`/home/alaabadawii/DevOps/Manara/devops-lap/app/app.py`
`/home/alaabadawii/DevOps/Manara/devops-lap/tests/test_app.py`
`git log` within `/home/alaabadawii/DevOps/Manara/devops-lap/`