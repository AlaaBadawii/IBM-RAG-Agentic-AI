# I Accidentally Committed an SSH Key to Git

## Type

Failure / Mistake

## Context

During the Packt DevOps Bootcamp practice
(`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/`), AWS CLI was set up and an
EC2 SSH key (`devops.pem`) was created for cloud practice.

## Problem

The private key file ended up tracked in the git repo. The repository had no
`.gitignore`, so a real EC2 SSH private key was committed.

## What I Did

Recognized the mistake after the fact (the `.pem` file is present in the repo).
It was practice, not a production breach, but it surfaced a real gap in my
workflow: no ignore rules for secret material.

## Decision / Insight

Secret material belongs in secret stores or gitignored environment files —
never in a repository. A `.gitignore` is not optional; it is the first line of
defense for credentials.

## Result

The lesson is documented in the KB (a personal, honest mistake). The key was
practice-only, so no real system was exposed — but the principle stands.

## Engineering Lesson

Credential hygiene is an engineering concern from the very first commit. Ignore
rules should be in place before the first `git add`, not after a leak.

## Why This Matters

Production engineering means owning secrets safely. A mistake early in learning
is exactly the kind of honest story that shows growth — as long as it is framed
as a mistake, not as expertise.

## Evidence

- `/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/devops.pem` (the committed key)
- KB: `completed_projects/docker_nginx_packt_bootcamp.md` (Security lesson),
  `evidence/devops/devops.md`

## Content Potential

- Failure/mistake story ("I committed an SSH key — here's what I learned")
- Credential-hygiene lesson post
- Contrast: this is a mistake, not a claim of security expertise

Story strength:
MEDIUM

Reason:
A real, first-hand mistake with concrete evidence and an honest lesson. It is
framed as a mistake rather than an achievement, which is honest — but the
"result" is primarily a lesson learned, not a system-level fix.
