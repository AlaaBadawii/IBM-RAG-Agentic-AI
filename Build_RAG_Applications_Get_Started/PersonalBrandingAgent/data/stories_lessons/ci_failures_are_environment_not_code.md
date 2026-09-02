# Most CI Failures Are Environment, Not Code

## Type

Debugging

## Context

A tiny Flask app used to practice CI with **Jenkins** and **GitHub Actions**
(`/home/alaabadawii/DevOps/jenkins-practice/`). The app and its tests were
trivial; the pipeline kept failing anyway.

## Problem

The pipeline was red even though `pytest` passed locally. `tests/test_app.py`
does `from app import app`, which requires the repo root to be importable — but
the way pytest was invoked in CI meant the module wasn't found.

## What I Did

Worked through the git history committing fix after fix: switched from a host
venv to a clean `docker run` environment, added `PYTHONPATH=.` to the Jenkins
step, and used `python -m pytest` in GitHub Actions. The real debugging was
about *how* the tests were invoked, not the test logic itself.

## Decision / Insight

When CI is red, check **cwd, PATH, PYTHONPATH, and the environment** before
suspecting the app logic. `python -m pytest` sets `sys.path[0]` to the current
directory; plain `pytest` does not — one-line invocation differences cause
mysterious import failures.

## Result

The pipeline turned green after aligning the invocation with how the imports
were written. The same code that "failed" in CI passed once the environment
matched.

## Engineering Lesson

A failing pipeline is usually a signal about the environment, not the
correctness of the code. Reproducing the exact invocation locally is the fastest
way to isolate the cause.

## Why This Matters

Reliability and debugging judgment are core to the backend/production engineer
Alaa wants to become. "It works on my machine" is exactly the class of problem
that CI exists to catch — and this story shows hands-on debugging of it.

## Evidence

- `/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile`
- `/home/alaabadawii/DevOps/jenkins-practice/.github/workflows/ci.yml`
- `git log` inside `/home/alaabadawii/DevOps/jenkins-practice/` (commit titles
  like "Fix CI imports", "Use python -m pytest in CI")
- KB: `completed_projects/ci_cd_jenkins_github_actions.md`,
  `evidence/devops/devops.md`

## Content Potential

- Debugging story ("when CI is red, check the environment first")
- Short lesson on `python -m pytest` vs `pytest`
- "What I learned setting up CI" learning-by-building post

Story strength:
STRONG

Reason:
Concrete event, first-hand action over multiple commits, a clear technical
problem with a verifiable root cause and resolution, and an evidence trail in
git history. Shows real debugging persistence and judgment.
