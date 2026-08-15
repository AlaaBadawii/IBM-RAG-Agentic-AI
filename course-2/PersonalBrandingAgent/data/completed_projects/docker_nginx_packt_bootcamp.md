# Packt DevOps Bootcamp practice — Docker/nginx + AWS CLI setup

## Status
COMPLETED (built/practiced, local). Source:
`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/` (git repo,
origin `GitHub: AlaaBadawii/Packt-DevOps-Bootcamp`).

## What this is
Practice from the Packt DevOps Bootcamp covering (1) Docker image build with
nginx + healthcheck and (2) AWS CLI setup for cloud work.

## Evidence of built work
- `Dockerfile` — `FROM nginx:stable`, static `index.html` served at
  `/usr/share/nginx/html`, port via `ENV http_port=80`, `HEALTHCHECK`
  (`curl -f http://localhost:${http_port}/`), `nginx -g daemon off;`.
- `.dockerignore` — pattern-savvy: ignore everything (`**`) then allow only
  `!index.html`, so only the static page ships into the image.
- `app.py` (Flask hello-world, 2 routes) + `requirements.txt` — the app that
  complements the nginx static practice.
- `index.html` — static "Hello World" page.
- `aws/` — bundled **AWS CLI v2** distribution (with `install` script,
  `awscli`, `botocore`), i.e., AWS CLI installed locally for cloud practice.
- `devops.pem` — an AWS SSH private key (`-r--------`), indicating EC2 SSH
  provisioning was in progress.

## Git / collaboration practice
Commit history shows GitHub workflow practice:
- "Add addition and subtraction functions"
- "Enhance functionality based on #1"
- "This fixes #1"
(implies issue-driven development, e.g. branch/PR referencing issue #1.)

## Tools & concepts
Docker (nginx image, healthchecks, `.dockerignore` allow-lists), AWS CLI v2
install/configure, EC2 SSH keys (`.pem`), git/GitHub issue workflow.

## Lessons supported
- `.dockerignore` with a negated allowlist is how you keep an image minimal.
- Healthchecks make containerized services observable.

## Security lesson (authentic, do NOT repeat)
A private key file (`devops.pem`) was left inside the repository with no
`.gitignore`. Even for practice, private keys should never be committed.
This is a real, honest lesson about credential hygiene worth telling — not
a claim of secure production handling.

## Accurate classification
PRACTICED/BUILT (images + CLI setup). No evidence of actually deploying to
AWS (no terraform, no `aws` commands in git history, no pushed infra). The
`.pem` suggests EC2 access existed but is unverified.

## Provenance
`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/Dockerfile`
`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/.dockerignore`
`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/aws/README.md`
`git log` within `/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/`