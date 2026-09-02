# FastAPI — Shipments API practice lab

## Status
IN PROGRESS (early-stage practice lab; functionally complete CRUD, no tests,
no git, no docs). Source: `/home/alaabadawii/FastAPI/`.

## What this is
A small FastAPI + SQLModel practice project: a "Shipment API" with full CRUD
over a local SQLite database (`shipments.db`), plus a standalone async lab
file. Last modified 2026-08-07. It lives in its own repo folder with a
dedicated virtualenv (`fastapi_venv/`). There is NO README, no requirements.txt,
no pyproject.toml, no .git, and no tests — the fastest parts are the source
files themselves.

## Project architecture (evidence: `app/`)
```
FastAPI/
├── app/
│   ├── __init__.py          (empty package marker)
│   ├── main.py              FastAPI app, lifespan, all 6 routes, uvicorn entry
│   ├── schemas.py           SQLModel/Pydantic schema layer (Shipment* classes, status enum)
│   └── database/
│       ├── __init__.py      (empty)
│       ├── session.py       engine, create_db_and_tables, get_session, SessionDep
│       └── models.py        duplicate Shipment table model (UNUSED by main.py)
├── async.py                 standalone asyncio lab (TaskGroup, gather)
├── shipments.db             local SQLite DB (4 rows persisted)
└── fastapi_venv/            virtualenv (fastapi, sqlmodel, uvicorn, pydantic, sqlalchemy, rich)
```
Layered layout: `routes (main.py) → schemas (schemas.py) → DB session
(database/session.py)` — a clean model/route/session split that mirrors the
`Route → Service → Model` discipline used in Quizey_V2, though there is no
separate service layer here.

## What I actually implemented (evidence-backed)

### Endpoints (all in `app/main.py`)
| Method | Path | Returns | Status |
|---|---|---|---|
| GET | `/` | `{"message": "Hello World"}` | 200 |
| GET | `/shipments` | `ShipmentGetallResponse` (dict of id→shipment) | 200 |
| GET | `/shipment/{id}` | `ShipmentResponse` | 200 / 404 |
| POST | `/shipment` | `ShipmentResponse` (201) — auto-sets `estimated_delivery = now+7d`, `status=PENDING` | 201 |
| PUT | `/shipment/{id}` | `ShipmentResponse` — full update | 200 / 404 |
| PATCH | `/shipment/{id}` | `ShipmentResponse` — partial update | 200 / 404 |
| DELETE | `/shipment/{id}` | `ShipmentDeleteResponse` (returns deleted record) | 200 / 404 |

### Behaviour implemented
- `lifespan` asynccontextmanager — creates tables on startup, prints a
  "Shutting down..." Rich panel on shutdown (`main.py:23-28`, `main.py:31`).
- 404 handling via `HTTPException` for missing ids on GET/PUT/PATCH/DELETE.
- Partial update pattern: `model_dump(exclude_none=True)` so only provided
  fields are written (`main.py:94-95`, `main.py:114-115`).
- Create defaulting: `datetime.now().date() + timedelta(days=7)` and
  `ShipmentStatus.PENDING` (`main.py:72-73`).
- `response_model=` + explicit `status_code=` on every route — typed,
  documented responses.
- DB persistence confirmed: `shipments.db` contains a real `shipments` table
  with 4 rows (Egypt→Cairo/Giza/Sharqia weight 12.0 PENDING; NY→LA weight 10.5
  PENDING; estimated_delivery 2026-08-11), i.e., the POST/GET path ran against
  the live DB.

## FastAPI concepts practiced (evidence)
- FastAPI route decorators, path params (`{id}`), `status_code` constants.
- `Annotated` dependency injection: `SessionDep = Annotated[Session, Depends(get_session)]`
  (`session.py:22`).
- Response models (`response_model=`) for typed, documented responses.
- App lifecycle via `asynccontextmanager` lifespan.
- Request-body models as function parameters (Pydantic validation).
- Running via uvicorn (`main.py:138-141`, `uvicorn.run(app, host=0.0.0.0, port=8000)`).

## Pydantic/SQLModel/schema usage (evidence: `app/schemas.py`)
- `ShipmentStatus(Enum)` — PENDING / IN_TRANSIT / DELIVERED.
- `ShipmentBase` — shared `origin` / `destination` / `weight` fields with
  `Field(..., description=...)` docs.
- `Shipment(ShipmentBase, table=True)` — **table model** (id, estimated_delivery,
  status).
- Request vs response separation: `ShipmentCreate` (input) vs `ShipmentResponse`
  (output, includes id/date/status) vs `ShipmentUpdate` (all optional) vs
  `ShipmentDeleteResponse` (echoes deleted record).
- `ShipmentGetallResponse` — response wrapper `dict[int, Shipment]`.
- `model_dump()` / `model_dump(exclude_none=True)` used for create/update.
- Field metadata: descriptions on every field; `weight` documented in kg.

## Async programming (evidence: `async.py` + `main.py`)
- `async.py` — standalone asyncio lab: `async def end_point()` simulating
  processing with `await asyncio.sleep(1)`; runs 3 tasks concurrently with
  `asyncio.gather(*tasks)` and again with `asyncio.TaskGroup()`, timing the
  total with `asyncio.get_event_loop().time()`. Run via `asyncio.run(server())`.
- `main.py` — async lifespan (asynccontextmanager), and the FastAPI app itself
  (async-capable even though route handlers are currently `def`, not `async def`).
- **Honest scope:** the async shown is beginner-level — one sleep-based demo and
  an async lifespan. No async DB driver, no `async def` route handlers, no
  background tasks, no production concurrency patterns.

## Database usage (evidence: `app/database/session.py`)
- SQLAlchemy/SQLModel engine: `create_engine(f"sqlite:///{DB_PATH}", echo=True)`
  where `DB_PATH = FastAPI/shipments.db` (`session.py:7-8`).
- `SQLModel.metadata.create_all(bind=engine)` for table creation
  (`session.py:11-13`).
- Session management via a generator dependency + `SessionDep`
  (`session.py:16-22`).
- Read/write patterns: `session.exec(select(Shipment))`, `session.get(Shipment, id)`,
  `session.add/commit/refresh`, `session.delete`.
- SQLite only (no MySQL/Postgres here). Real DB has 4 persisted rows.

## Testing
- **NO tests found.** No `test_*.py` files anywhere outside the venv, no
  pytest/unittest scaffolding, no test directory. The API is verified only by
  manual exercise (evidenced by the 4 rows in `shipments.db`).

## Problems / bugs / observations (evidence-backed)
1. **Duplicate, unused table model:** `app/database/models.py` defines its own
   `Shipment` (with `weight: float = Field(le=25)` — a max-weight constraint),
   but `main.py` imports `Shipment` from `app.schemas` instead. So `models.py`
   is dead code and its `weight <= 25` validation is NOT enforced anywhere.
2. **The `le=25` weight constraint exists in exactly one of the two duplicate
   definitions** — inconsistent validation between the two Shipment classes.
   Whether intentional or not, it is currently inert.
3. **No README / requirements.txt / pyproject / .git** — the project is not
   reproducible from this folder alone (deps live only in the venv), mirroring
   the same gap noted in Quizey_V2 (`requirements.txt` empty there too).
4. **Duplicate table-model + schema-model pattern:** FastAPI/SQLModel commonly
   separates *input schemas* from *table models*, but here the table model
   itself (`Shipment(table=True)`) lives inside `schemas.py` and is re-imported
   by the API, blurring the schema/model separation.
5. **Minor style:** PATCH and PUT share identical logic (no distinction between
   full vs partial semantics); `estimated_delivery` is server-derived on create
   but client-suppliable on update.
6. **Root endpoint returns plain dict** while everything else uses
   `response_model` — minor inconsistency.

## Lessons learned (as of this state)
- FastAPI + SQLModel gives typed request/response models and automatic OpenAPI
  docs with very little code.
- Dependency injection via `Annotated` keeps sessions per-request without
  manual plumbing.
- Lifespan contexts are the idiomatic place for startup/teardown (table
  creation) in modern FastAPI (vs deprecated `on_event`).
- Real risk surfaced by the code: duplicate model definitions silently
  deactivate constraints — a good "small mistakes in practice" story, but
  currently unsupported by tests or docs.

## Current status
- **Completed (local):** working CRUD API (6 routes) against SQLite with 4
  persisted test rows; a runnable async demo (`async.py`); a populated venv.
- **In progress / unfinished:** no tests, no README, no dependency manifest, no
  git, unused duplicate model in `database/models.py`, `le=25` constraint not
  enforced.
- **Planned (nothing documented):** there is no plan/README indicating next
  steps.

## Accurate classification (do not overclaim)
This is a **practice/learning lab** that demonstrates working FastAPI CRUD,
SQLModel schemas, dependency injection, lifespan, and basic asyncio — all at a
starter level. There is no professional or production FastAPI experience to
claim here: no tests, no deployment, no async database layer, no CI, no docs.
Treat it as "I can build a working FastAPI CRUD API and reason about async" —
not "production FastAPI engineer".

## Provenance / evidence files
- `/home/alaabadawii/FastAPI/app/main.py` — app + all routes + lifespan + uvicorn.
- `/home/alaabadawii/FastAPI/app/schemas.py` — schema layer (Shipment*, enum).
- `/home/alaabadawii/FastAPI/app/database/session.py` — engine, session, SessionDep.
- `/home/alaabadawii/FastAPI/app/database/models.py` — unused duplicate Shipment (le=25).
- `/home/alaabadawii/FastAPI/async.py` — asyncio gather/TaskGroup lab.
- `/home/alaabadawii/FastAPI/shipments.db` — 4 persisted rows (SQLite).
- `/home/alaabadawii/FastAPI/fastapi_venv/` — packages: fastapi 0.139.2,
  sqlmodel 0.0.39, pydantic 2.13.4, uvicorn 0.51.0, sqlalchemy 2.0.51, rich 15.
- `.vscode/settings.json` — points default interpreter at `fastapi_venv`.
