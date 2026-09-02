# Evidence Layer

Answers one question:

> **What can Alaa publicly claim he has actually done, based on concrete evidence?**

This layer lets the Personal Branding Agent distinguish **demonstrated ability /
documented experience / completed work** from **in-progress work / learning /
aspirations / unverified claims** — supporting the writing rule:
*Demonstrated ability over claims.*

## How to use

1. To make a factual/public claim, first find the supporting evidence item(s)
   here. If there is none, the claim must be softened (e.g., "learning",
   "building", "in progress") or dropped.
2. Every item carries an **Evidence state** and a **Publicly safe claim**.
3. Do not invent evidence. `EVIDENCE: insufficient` is preferred over guessing.

## Evidence states

| State | Meaning |
|---|---|
| VERIFIED | Strong concrete evidence (repo/implementation details, demonstrated implementation). |
| DOCUMENTED | Documented in the KB but not independently verified. |
| IN_PROGRESS | Capability/work exists but is not complete. |
| LEARNING | Currently learning; no substantial implementation demonstrated. |
| ASPIRATIONAL | Wanted/future capability, not yet demonstrated. |
| UNVERIFIED | Claim exists somewhere but evidence is insufficient. |
| STALE | Was once valid, superseded by newer info (e.g., old test counts). |

## Evidence hierarchy (when sources conflict, highest wins)

1. Current repository/source evidence
2. Explicit project documentation
3. Current KB project files
4. Audit conclusions
5. Portfolio / public positioning
6. Course / certificate descriptions
7. Inference (never used to manufacture evidence)

## Index

| Area | File | Contents |
|---|---|---|
| Flagship project | `projects/quizey_v2.md` | Quizey V2 backend/AI/DevOps evidence, test counts, claims. |
| Flagship project | `projects/quizey_v1.md` | Old ALX Quizey (a.k.a. Quizey V1) — distinct. |
| Other projects | `projects/other-completed-projects.md` | Taskey, AirBnB clone, Files Manager, simple_shell, ALX, genAI/book-app. |
| AI | `ai/ai_agents_from_scratch.md` | 3 framework-free agents (earlier milestone). |
| AI | `ai/evaluator_core.md` | Judge+Critic grading engine (later build, in progress). |
| AI | `ai/rag_learning_and_application.md` | RAG course learning vs Personal Branding Agent RAG practice. |
| Backend | `backend/fastapi.md` | FastAPI Shipment API practice lab. |
| Backend | `backend/databases.md` | MongoDB/PyMongo, SQLAlchemy/MySQL/SQLite/PostgreSQL. |
| DevOps | `devops/devops.md` | Docker, Compose, CI/CD, AWS, Kubernetes. |
| Professional | `professional/professional.md` | FlyRank, Alignerr, programs, badges. |
| Learning | `learning/learning_evidence.md` | Courses/certs → what they actually enabled. |

## Key source references

- `../audit/cross_source_audit.md` — canonical flags (unverified claims, stale
  counts, Docker/AI tag corrections).
- `../in_progress_projects/` — authoritative current state of in-progress work
  (Quizey V2, Evaluator Core, FastAPI, K8s lab).
- `../completed_projects/` — completed project detail.
- `../vision_goals/my_vision.md` — vision (controlled separately; not inferred).