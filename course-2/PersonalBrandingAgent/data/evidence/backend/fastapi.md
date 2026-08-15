# FastAPI — Evidence

FastAPI Shipment API practice lab. Source:
`../in_progress_projects/fastapi_shipment_api.md`, repo `/home/alaabadawii/FastAPI/`.

## Evidence state

IN_PROGRESS (practice lab: working CRUD; no tests/git/docs).

## What was actually built (evidence-backed)

- FastAPI app (`app/main.py`) with 6 routes: `/`, `GET /shipments`,
  `GET/POST/PUT/PATCH/DELETE /shipment/{id}` over a local SQLite DB
  (`shipments.db`, 4 persisted rows).
- `lifespan` asynccontextmanager for startup table creation / teardown.
- 404 via `HTTPException`; partial update with `model_dump(exclude_none=True)`;
  create defaults `estimated_delivery = now+7d`, `status=PENDING`.
- `response_model=` + explicit `status_code=` on each route.
- Schema layer (`app/schemas.py`): `ShipmentStatus` enum, `ShipmentBase`,
  table model `Shipment`, request/response classes, `ShipmentGetallResponse`.
- Dependency injection via `Annotated[Session, Depends]` / `SessionDep`.
- Async lab (`async.py`): `asyncio.gather` + `TaskGroup`, timing.

## Honest scope (do not overclaim)

- **Beginner-level practice lab, not production.** No tests, no deployment, no
  async DB driver, no `async def` route handlers, no CI, no docs, no git.
- Duplicate unused `Shipment` table model in `app/database/models.py` (the
  `weight le=25` constraint is inert); PATCH and PUT share identical logic;
  `requirements.txt`/README absent.

## Technologies demonstrated (starter level)

FastAPI, SQLModel/Pydantic, SQLAlchemy, uvicorn, Python asyncio.

## Publicly safe claim

- "I can build a working FastAPI CRUD API and reason about async basics."
- "I built a FastAPI shipment API with typed request/response models, dependency
  injection, and a SQLite database."

## Avoid

- "Production FastAPI engineer." (exercise/project not production.)

## Relationship

- Mirrors the `Route → Service → Model` discipline used in Quizey V2
  (`projects/quizey_v2.md`), though no separate service layer here.

## Evidence source

`../in_progress_projects/fastapi_shipment_api.md`, `/home/alaabadawii/FastAPI/app/`
(`main.py`, `schemas.py`, `database/`), `async.py`, `shipments.db`,
`fastapi_venv/` (fastapi 0.139.2, sqlmodel 0.0.39, pydantic 2.13.4, uvicorn).