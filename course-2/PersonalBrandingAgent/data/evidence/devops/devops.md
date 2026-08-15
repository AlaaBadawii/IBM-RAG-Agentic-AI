# DevOps — Evidence

Separates **demonstrated** from **currently learning** from **future target**.
Calibrate each technology to its actual state. Primary sources:
`../completed_projects/docker_compose_flask_mysql_app.md`,
`../completed_projects/docker_nginx_packt_bootcamp.md`,
`../completed_projects/ci_cd_jenkins_github_actions.md`,
`../in_progress_projects/kubernetes_manara_lab.md`,
`../in_progress_courses/practical_devops_bootcamp_packt.md`.

## Demonstrated (VERIFIED / completed labs)

### Docker
- **Evidence:** Dockerfile + `docker-compose.yml` (Flask+MySQL, multi-service,
  `depends_on`, named volume) — `docker_compose_flask_mysql_app.md` (COMPLETED);
  Docker/nginx practice in the Packt bootcamp (`docker_nginx_packt_bootcamp.md`);
  per-agent Dockerfiles in AI Agents. Also Docker-in-CI in Jenkins.
- **Publicly safe claim:** "I containerize apps with Docker and orchestrate
  multi-service setups with Docker Compose." | Lab-level, local; **not** production
  orchestration.

### CI/CD
- **Evidence:** Jenkins declarative pipeline (test stage in Docker) + GitHub
  Actions `.github/workflows/ci.yml`; 15-commit debugging history over module/
  `PYTHONPATH`/venv-vs-container issues (`ci_cd_jenkins_github_actions.md`,
  COMPLETED).
- **Publicly safe claim:** "I set up CI for a Flask app with both Jenkins and
  GitHub Actions, including debugging import/environment issues."
- **Avoid:** "I deploy / production CI/CD." Single test stage; **no deploy stage**.

### AWS / cloud
- **Evidence:** AWS CLI v2 install + an EC2 `.pem` (setup only) — `docker_nginx_packt_bootcamp.md`.
- **Publicly safe claim:** essentially none beyond "I've set up the AWS CLI";
  no EC2-hosted workload, no managed-service deployment evidenced. Treat as
  LEARNING/setup.

## Currently learning (LEARNING / IN_PROGRESS)

- **Kubernetes** — `kubernetes_manara_lab.md` (IN PROGRESS / early): minikube
  binary downloaded, a first `Deployment` manifest for nginx that **contains
  invalid label keys** (`matchLables`/`lables` — misspelled) and would be rejected
  by `kubectl apply`; notes/commands files empty. No running cluster, no service/
  ingress, no workload.
- **Publicly safe claim (honest):** "I'm starting to learn Kubernetes (minikube,
  writing a first Deployment manifest)."
- **Avoid:** "Kubernetes competency" — audit §B4 + the lab itself say keep it
  in-progress/early. Do not claim to operate a cluster.
- **Packt Practical DevOps Bootcamp** (course IN PROGRESS; C1 complete, C2
  Containerization & K8s at 75%, C3 not started). This is learning; the completed
  labs above are practice. Not contradictory.

## Future target (ASPIRATIONAL)

- Monitoring, observability, cloud infrastructure (deeper), git ops — from vision
  `../vision_goals/my_vision.md`; not yet demonstrated.

## Relationship to Quizey V2

- Docker is demonstrated in **separate** DevOps projects, **not** in Quizey V2.
  Do not attach "Docker"/"AI" tags to Quizey V2 (see `projects/quizey_v2.md`).

## DevOps course vs completed labs (not contradictory)

- The Packt/Manara DevOps **program** is in progress, but individual labs
  (Docker Compose app, nginx, Jenkins CI) are completed. State both accurately:
  labs completed + course ongoing.

## Evidence source

See bullets + `/home/alaabadawii/DevOps/` (Manara `devops-lap`,
`Kubernetes_lab`, `jenkins-practice`, `Packt-DevOps-Bootcamp`).