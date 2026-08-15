# Jenkins CI/CD practice — Flask app with Jenkins + GitHub Actions

## Status
COMPLETED (practiced/built, local CI + GitHub Actions). Source:
`/home/alaabadawii/DevOps/jenkins-practice/` (git repo,
origin `GitHub: AlaaBadawii/jenkins-practice`).

## What this is
A tiny Flask app used to practice continuous integration with **Jenkins** and
**GitHub Actions**. The value is not the app (it's a hello-world) but the
pipeline work and, especially, the debugging history in git.

## Evidence of built work
- `Jenkinsfile` — declarative pipeline running tests inside a Docker container:
  `docker run --rm -v $WORKSPACE:/app python:3.10-slim` + `pip install` +
  `PYTHONPATH=. pytest`.
- `.github/workflows/ci.yml` — GitHub Actions: on push/PR to main,
  checkout → setup-python 3.10 → install deps → `python -m pytest -v`.
- `Dockerfile` — `python:3.10-slim` Flask app image (port 5000).
- `app/`, `tests/` — Flask app (`/`, `/health`) + pytest tests.
- `venv/` + `.pytest_cache/` — local development.

## Debugging experiences (from git history — real CI struggles, 15 commits)
The commit log shows an iterative fight to get CI green:
- "Initial Jenkins practice app"
- "Add Jenkins pipeline file"
- "Add CI stages: install + test"
- "Fix Jenkins pipeline with venv" (multiple times)
- "Fix CI using Docker instead of venv"
- "Fix PYTHONPATH for CI"
- "Fix CI imports and clean pipeline"
- "Use python -m pytest in CI" (multiple times)

Root cause visible in the code: `tests/test_app.py` does `from app import app`,
which needs the repo root on `PYTHONPATH`; running `pytest` from the wrong cwd
fails. Fixed by `PYTHONPATH=. pytest` (Jenkinsfile) and `python -m pytest`
(GitHub Actions).

## Tools & concepts
Jenkins (declarative pipeline), GitHub Actions, Docker-in-CI, venv vs container
environments, `PYTHONPATH`/module import resolution, pytest.

## Lessons supported
- CI debugging is mostly about *environment* (cwd, PATH, PYTHONPATH), not test
  logic.
- Running tests in a clean Docker container removed host-venv flakiness
  ("Fix CI using Docker instead of venv").
- `python -m pytest` sets `sys.path[0]` to cwd, fixing imports that plain
  `pytest` misses.

## Accurate classification
BUILT (local practice, pushed to GitHub). Jenkins pipeline is a single
test stage — no deploy stage present. Do not claim production CI/CD or
Kubernetes deployment.

## Provenance
`/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile`
`/home/alaabadawii/DevOps/jenkins-practice/.github/workflows/ci.yml`
`/home/alaabadawii/DevOps/jenkins-practice/Dockerfile`
`git log` history within `/home/alaabadawii/DevOps/jenkins-practice/`