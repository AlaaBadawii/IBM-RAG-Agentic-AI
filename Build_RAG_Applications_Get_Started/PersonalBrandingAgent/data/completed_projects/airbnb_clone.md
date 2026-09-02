# AirBnB Clone (HBnB) — multi-stage full-stack project

## Status
Completed. Treated as a portfolio project. Repos under `GitHub: AlaaBadawii/AirBnB_clone*`.

## What this is
A multi-stage Airbnb-style application built across the ALX curriculum. It is one
continuous project developed incrementally over several milestones: console ->
web framework -> RESTful API -> dynamic frontend.

## Stages actually implemented

### Stage 1 — Console + JSON FileStorage (v1)
`/home/alaabadawii/ALX/AirBnB_clone`
- Command-line interpreter (`console.py`) using Python `cmd` module.
- OOP model layer: `BaseModel` parent class with `User`, `State`, `City`,
  `Amenity`, `Place`, `Review` subclasses (`models/`).
- JSON serialization / deserialization persistence via a swappable storage
  engine (`models/engine/file_storage.py`).
- Interactive and non-interactive (piped) modes; CRUD + `all`/`show`/`count`.
- Evidence: `console.py`, `models/base_model.py`, `models/engine/file_storage.py`,
  `file.json`, `tests/`.

### Stage 2 — Web framework + MySQL/SQLAlchemy (AirBnB_clone_v2)
- Flask web server on `0.0.0.0:5000` with dynamic routing and Jinja templates
  (`web_flask/`).
- Added a second storage engine: SQLAlchemy ORM `DBStorage` against MySQL,
  switchable at runtime via the `HBNB_TYPE_STORAGE` env var (file vs db).
- Session management with `teardown_appcontext`, state/city relationship
  getters, alphabetical sorting.
- SQL schemas for dev/test (`setup_mysql_dev.sql`, `setup_mysql_test.sql`).
- Evidence: `web_flask/`, `models/engine/db_storage.py`, README "Enhancements &
  DB Storage Integration" section.

### Stage 3 — RESTful API (v3 / v4)
- Flask blueprints (`api/v1/views/`) exposing CRUD endpoints for every model.
- JSON responses, custom 404 error handler, CORS enabled.
- `GET /status` and `GET /stats` endpoints (`api/v1/views/index.py`).
- Many-to-many Place<->Amenity management specialized in
  `api/v1/views/places_amenities.py`.
- Evidence: `api/v1/app.py`, `api/v1/views/*.py`.

### Stage 4 — API documentation + dynamic frontend (v4)
- Flasgger/OpenAPI (Swagger) docs for all endpoints
  (`api/v1/views/documentation/**/*.yml`).
- jQuery-based dynamic pages pulling data from the API (`web_dynamic/`).
- Evidence: `api/v1/views/documentation/`, `web_dynamic/static/scripts/1-hbnb.js`.

## Technologies
Python 3, Flask, Flask-CORS, Flask-REST blueprints, SQLAlchemy ORM, MySQL,
Jinja2, JSON, the `cmd` module, Flasgger/Swagger, jQuery, JavaScript, shell scripts
(Fabric-style deploy scripts present in v3/v4: `0-`, `1-`, `2-`, `3-do_deploy_web_static.py`).

## Backend concepts practiced
- Object serialization/deserialization to files.
- ORM (SQLAlchemy) versus raw file storage; runtime storage-engine selection.
- Relational modeling incl. many-to-many (Place-Amenity).
- RESTful resource design, HTTP verbs, blueprints/bundles, error handling.
- Database schema management and dev/test DB setup.
- Session lifecycle management.

## Software engineering concepts practiced
Incremental development of the same codebase across stages; separation of
storage engines behind a common interface; unit tests; documentation-first API
design (Swagger).

## Lessons supported by work
- Building a storage abstraction lets the same app run on different backends
  (file vs MySQL) — an interface-design win.
- A single project can cross the whole stack when grown in stages.

## Ownership note
This is an ALX curriculum project. `README.md` in v3/v4 were adapted from the
course's reference template README and still credit Holberton-era authors; all
remote origins point to AlaaBadawii's GitHub, so the completed repo is held and
maintained by Alaa.

## Reported skill level (accurate, not inflated)
Comfortable, working OOP in Python, CRUD REST APIs in Flask, and SQLAlchemy/MySQL
integration at a course-project level. Not production-hardened (no heavy auth on
this API, no real deployment to the cloud for this API shown).

## Evidence / key files
`/home/alaabadawii/ALX/AirBnB_clone/console.py`
`/home/alaabadawii/ALX/AirBnB_clone_v2/web_flask/`
`/home/alaabadawii/ALX/AirBnB_clone_v2/models/engine/db_storage.py`
`/home/alaabadawii/ALX/AirBnB_clone_v3/api/v1/views/`
`/home/alaabadawii/ALX/AirBnB_clone_v4/api/v1/views/places_amenities.py`
`/home/alaabadawii/ALX/AirBnB_clone_v4/api/v1/views/documentation/`
`/home/alaabadawii/ALX/AirBnB_clone_v4/web_dynamic/`