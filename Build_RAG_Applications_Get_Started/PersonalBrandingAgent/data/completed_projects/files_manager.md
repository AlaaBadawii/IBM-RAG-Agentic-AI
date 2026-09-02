# Files Manager — Node.js/Express file management API

## Status
Completed ALX course project (individual repo, remote origin
`GitHub: AlaaBadawii/alx-files_manager`). Built on the ALX/Holberton course
scaffold — the codebase's own `package.json`/README attribute the original
template author (Karim Awudulai). Alaa completed and holds the project.

## What this is
A file management REST API: user auth, file upload/pagination/visibility,
authentication tokens, thumbnail generation and welcome emails via background
jobs, MongoDB for data, Redis for job queuing/token management.

## Evidence of implemented
`/home/alaabadawii/ALX/alx-files_manager/`
- `server.js`, `worker.js` — HTTP server + Bull background worker.
- `controllers/` — `AppController.js`, `UsersController.js`, `AuthController.js`,
  `FilesController.js`.
- `utils/` — `db.js` (MongoDB), `redis.js`, `auth.js`, `mailer.js` (Google
  Gmail API), `env_loader.js`.
- `middlewares/` — `auth.js`, `error.js`.
- `routes/index.js`; ESLint (airbnb) + Mocha/Chai tests; Yarn/npm tooling.

## Technologies
Node.js (Babel ES modules), Express, MongoDB, Redis, Bull (job queue),
googleapis (Gmail), image-thumbnail, SHA1 password hashing, UUID, Mocha/Chai.

## Backend concepts practiced
- NoSQL (MongoDB) data access and ObjectId handling.
- Redis caching/queueing; Bull background job processing (image thumbnails at
  widths 500/250/100, welcome emails).
- Token-based auth for file endpoints.
- File upload storage and metadata management.
- Background/async processing decoupled from request lifecycle.

## Software engineering concepts practiced
Separation of controllers/middleware/utils; queue-based worker architecture;
ESLint + unit/E2E test tooling; dotenv config.

## Lessons supported
- Real exposure to a JS backend beyond CRUD: async workers, caching, third-party
  APIs (Gmail).

## Reported skill level (accurate, not inflated)
Course-completion level. Large share of the architecture is the ALX-provided
template, so authorship/ownership of the design should be stated honestly. The
worker/controller/service structure was implemented/assembled by the student as
part of the tasks.

## Evidence / key files
`/home/alaabadawii/ALX/alx-files_manager/package.json`
`/home/alaabadawii/ALX/alx-files_manager/worker.js`
`/home/alaabadawii/ALX/alx-files_manager/controllers/`
`/home/alaabadawii/ALX/alx-files_manager/utils/`
`/home/alaabadawii/ALX/alx-files_manager/README.md`