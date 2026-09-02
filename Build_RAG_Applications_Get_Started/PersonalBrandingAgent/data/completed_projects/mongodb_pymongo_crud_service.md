# MongoDB / PyMongo practice — CRUD service + query app

> **Distinct-projects note (from the cross-source audit):** MongoDB appears in
> several SEPARATE KB entries — this one (Python/PyMongo, from `DataBases/`),
> **Files Manager** (`../completed_projects/files_manager.md`, Node/Express +
> MongoDB/Redis/Bull, an ALX project), and the curriculum modules in
> `../completed_projects/alx_backend_engineering.md`. These are different
> projects (Python practice vs Node app vs ALX study); do not merge them.

## Status
COMPLETED (implemented as practice; local lab). Source:
`/home/alaabadawii/DataBases/MongoDB/`.

## What this is
A standalone MongoDB practice project using PyMongo: a `StudentsService` CRUD
layer plus a restaurant-query app, backed by a local MongoDB (`localhost:27017`)
and the classic MongoDB "restaurants" sample dataset. This is the only content
in `/home/alaabadawii/DataBases/` (PostgreSQL/MySQL/etc. live in other repos).

## Evidence (actual files)
- `database.py` — connects `pymongo.MongoClient("mongodb://localhost:27017/")`,
  selects `pymongo_lab` DB and `students` collection.
- `student_service.py` — full CRUD wrapper around the `students` collection:
  - `create_student(name, age, email)` → `insert_one` → returns `inserted_id`.
  - `get_student_by_email`, `get_all_students`, `get_student(key, value)`.
  - `get_student_above_age` / `get_students_with_age_less_than` — `$gt` / `$lt`.
  - `update_student_email` / `update_student` — `update_one` + `$set`.
  - `increment_student_age` — `$inc`.
  - `delete_student` — `delete_one` by `ObjectId`.
  - `delete_student_by_email` — soft delete via `$set: {is_deleted: true}`.
- `app.py` — `sort_restaurants(cuisine)`; queries the `restaurants` collection
  and sorts results.
- `primer-dataset.json` — MongoDB's official "restaurants" sample dataset
  (address/borough/cuisine/grades arrays) used for import/querying.
- Dependency file (misspelled `requrements.txt` in the repo): `pymongo==4.17.0`,
  `dnspython==2.8.0` (DNS for Atlas-style SRV connection strings).
- `venv/` — local env with `pymongo 4.17.0` confirmed.

## Concepts demonstrated by code (not just read)
- CRUD against a document store (`insert_one`, `find_one`, `find`, `update_one`,
  `delete_one`).
- Query operators `$gt` / `$lt`; update operators `$set` / `$inc`.
- ObjectId primary keys; handling BSON ids in Python.
- Collection/document modeling in a NoSQL document DB.
- Working with an embedded array field (`grades`, `address.coord`) from the
  sample dataset.

## Technical observation (honest)
`app.py`'s `sort_restaurants` is buggy/rough:
- It uses `sort({"orange": 1})` (a non-existent key) instead of an actual sort
  field, and `sort()` is passed a dict rather than the conventional list of
  tuples/keynames. This looks like a work-in-progress / buggy first attempt
  (it otherwise defaults to sorting by `name`). No tests exist, so treat
  "query/sort" as PRACTICED with issues, not robust.

## Tools & concepts exercised
PyMongo 4.17, MongoDB local, CRUD, query/update operators, ObjectId, JSON
handling, dataset import.

## Classification summary
| Concept | Status |
| --- | --- |
| NoSQL / MongoDB (document model) | STUDIED + APPLIED |
| PyMongo CRUD operations | IMPLEMENTED (working methods) |
| Query/update operators ($gt/$lt/$set/$inc) | PRACTICED / IMPLEMENTED |
| Indexing / aggregation / transactions / migrations | NOT EVIDENCED here (covered in ALX storage + Quizey/PostgreSQL work elsewhere) |
| Sorting / optimization | PRACTICED (buggy attempt) |

## Provenance
`/home/alaabadawii/DataBases/MongoDB/student_service.py`
`/home/alaabadawii/DataBases/MongoDB/database.py`
`/home/alaabadawii/DataBases/MongoDB/app.py`
`/home/alaabadawii/DataBases/MongoDB/primer-dataset.json`
`/home/alaabadawii/DataBases/MongoDB/requirements.txt` (misspelled
`requrements.txt` in the repo)

## Cross-reference
The ALX curriculum already covers MongoDB shell + PyMongo scripts and MySQL
(see `data/completed_projects/alx_backend_engineering.md`). PostgreSQL and the
rest of the relational stack are expected in the Quizey_V2 work (not yet present
in `/home/alaabadawii/DataBases/`).