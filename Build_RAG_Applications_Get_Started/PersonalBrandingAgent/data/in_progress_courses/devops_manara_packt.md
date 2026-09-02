# DevOps learning — Manara + Packt bootcamps (Docker, CI/CD, AWS, Kubernetes)

## Status
IN PROGRESS (active learning track). Sources under
`/home/alaabadawii/DevOps/` (Manara and Packt-DevOps-Bootcamp folders).

## Overview
Two learning tracks feed the DevOps work:
- **Manara** — a (MENA-focused) platform DevOps track: containerization lab
  (Flask+MySQL via docker-compose) and a Kubernetes lab (minikube).
- **Packt DevOps Bootcamp** — Docker/nginx images, AWS CLI setup, git/PR
  workflow practice.

## Per-technology status (studied / practiced / built / deployed / in progress)

| Technology | Status | Evidence |
| --- | --- | --- |
| Docker | PRACTICED / BUILT (local) | Dockerfiles (python, nginx) + docker-compose in Manara devops-lap, Packt |
| Docker Compose | BUILT (local) | `devops-lap/docker-compose.yml` (mysql:8 + flask) |
| CI/CD (Jenkins) | PRACTICED / BUILT (test stage) | `jenkins-practice/Jenkinsfile` |
| CI/CD (GitHub Actions) | PRACTICED / BUILT | `jenkins-practice/.github/workflows/ci.yml` |
| Kubernetes | IN PROGRESS (early) | `Manara/Kubernetes_lab/deployment.yaml`, minikube binary |
| AWS / cloud | PRACTICED (setup only) | `Packt/aws/` = AWS CLI v2 bundle; `devops.pem` (SSH key) |
| Linux / sysadmin | PRACTICED | ALX `system_engineering-devops` track (see ALX KB) |
| Networking / infra | STUDIED | ALX networking_basics, web_infrastructure design docs (see ALX KB) |

## Detailed practice notes
- **Docker**: multi-stage basics — build Flask app image vs static nginx image;
  `.dockerignore` allow-list (`**` + `!index.html`); `HEALTHCHECK`
  (curl-based), named volumes and `depends_on` for DB.
- **CI/CD both Jenkins and GitHub Actions** on the same app; heavy debugging of
  environment: `PYTHONPATH=.` vs `python -m pytest`; venv vs Docker run for
  tests.
- **AWS**: installed AWS CLI v2 (bundled distribution), created/kept an EC2 SSH
  `.pem`. No hardening — key committed to repo (see lessons).
- **Kubernetes**: minikube binary + first Deployment manifest (currently broken).

## Architecture / infra decisions made
- Compose-based local app+DB topology; env-var-driven config.
- Containerized CI test step rather than host venv (for reproducibility).

## Problems encountered & debugging
- CI import failures (module path/PYTHONPATH) — resolved over multiple commits.
- MySQL first-connection race (no db healthcheck gate).
- K8s manifest label typos (still unfixed).

## Lessons learned
- See `stories_lessons/devops_cicd_and_secret_handling.md` (commit nothing
  secret; CI env > test logic).
- Containerized CI removes environmental flakiness.

## Accurate note
All work is local lab/bootcamp practice. No evidence of production deployment,
managed Kubernetes (EKS/GKE), IaC (Terraform), or hardened, real AWS usage.
Do not present as professional production DevOps.

## Provenance
`/home/alaabadawii/DevOps/Manara/devops-lap/`
`/home/alaabadawii/DevOps/Manara/Kubernetes_lab/`
`/home/alaabadawii/DevOps/Packt-DevOps-Bootcamp/`
`/home/alaabadawii/DevOps/jenkins-practice/`