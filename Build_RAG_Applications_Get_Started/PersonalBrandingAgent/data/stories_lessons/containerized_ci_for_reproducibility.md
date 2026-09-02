# Containerized CI for Reproducibility

## Type

DevOps / Production

## Context

Same CI practice repo (`/home/alaabadawii/DevOps/jenkins-practice/`). After
fighting host-venv flakiness, the choice was between debugging the local venv
repeatedly or changing how tests run.

## Problem

Tests behaved differently between the host venv and CI. The local Python
environment was not reproducible, so each failure had to be re-diagnosed.

## What I Did

Switched the Jenkins test stage to run inside an ephemeral Docker container
(`python:3.10-slim`), mounting the workspace and running the tests in a clean
environment. This is visible in the commit log ("Fix CI using Docker instead of
venv").

## Decision / Insight

Clean, disposable environments are more predictable than shared ones. If the
container can run the tests, the environment is no longer a variable.

## Result

The containerized test step removed the host-venv flakiness; the pipeline became
reproducible across machines.

## Engineering Lesson

Reproducibility is a feature. Containerizing the test run takes "environment
drift" out of the equation so failures mean something.

## Why This Matters

This is a small step toward the production-engineering goal of taking products
from code to production. Reproducible environments are the foundation for
deployable systems.

## Evidence

- `/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile` (docker test stage)
- `git log` commit "Fix CI using Docker instead of venv"
- KB: `completed_projects/ci_cd_jenkins_github_actions.md`,
  `evidence/devops/devops.md`

## Content Potential

- DevOps lesson on reproducible environments
- "Why I run tests in a container" short post
- Learning-by-building story linking to Docker practice

Story strength:
STRONG

Reason:
A clear engineering decision (containerize the test run) with a documented
change in git history and a concrete outcome. Demonstrates judgment about
reproducibility, not just tool knowledge.
