# Databases — Evidence

Demonstrated database work across the KB, each tied to concrete evidence.

## MongoDB / PyMongo

- **Evidence state:** VERIFIED (implemented practice; local).
- **Evidence:** `../completed_projects/mongodb_pymongo_crud_service.md`,
  `/home/alaabadawii/DataBases/MongoDB/`.
- **What was built:** PyMongo 4.17 CRUD service (`StudentsService`: create/get/
  update/delete, `$gt`/`$lt`, `$set`/`$inc`, ObjectId, soft delete) + a
  restaurant-query app on the classic MongoDB "restaurants" dataset.
- **Honest note:** `sort_restaurants` is buggy/rough (sorts by non-existent key);
  no tests. Treat query/sort as PRACTICED with issues.
- **Publicly safe claim:** "I built a PyMongo CRUD service and query app against
  a local MongoDB document store."
- **Avoid:** "MongoDB expert." Separate from Files Manager (Node/MongoDB) and ALX
  storage coursework — do not merge.

## SQLAlchemy / MySQL / SQLite / PostgreSQL

- **Quizey V2** (IN PROGRESS): Flask-SQLAlchemy models, ~10 tables, Alembic
  migrations, MySQL dev / SQLite test (see `projects/quizey_v2.md`).
- **Quizey V1** (VERIFIED): SQLAlchemy + **PostgreSQL** + Alembic migrations (see
  `projects/quizey_v1.md`).
- **Taskey** (VERIFIED): Flask-SQLAlchemy models, SQLite fallback + optional MySQL.
- **AirBnB clone** (VERIFIED): SQLAlchemy + MySQL (stage 2+).
- **ALX coursework** (VERIFIED, coursework only): storage modules covering
  MySQL/MongoDB/Redis study (`../completed_projects/alx_backend_engineering.md`).

## Publicly safe claim

- "I've built database-backed apps with SQLAlchemy against SQLite, MySQL, and
  PostgreSQL, plus a PyMongo CRUD service against MongoDB."

## Avoid

- Claiming depth beyond evidence: no aggregation pipelines, transactions, or
  production tuning demonstrated for MongoDB; Postgres depth is limited to Quizey
  V1 + coursework.

## Evidence source

`../completed_projects/mongodb_pymongo_crud_service.md`,
`../completed_projects/quizey.md`, `../in_progress_projects/quizey_v2.md`,
`../completed_projects/taskey.md`, `../completed_projects/airbnb_clone.md`,
`../completed_projects/alx_backend_engineering.md`.