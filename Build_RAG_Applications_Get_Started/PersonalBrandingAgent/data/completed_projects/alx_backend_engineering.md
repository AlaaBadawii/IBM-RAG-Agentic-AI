# ALX curriculum — backend engineering, storage & DevOps

## Status
Studied / practiced (curriculum projects across six repo areas).

## Backend fundamentals — `/home/alaabadawii/ALX/alx-backend/`
- **Pagination** (`0x00-pagination`): simple, hypermedia, and deletion-safe
  pagination classes on real CSV data (`Popular_Baby_Names.csv`).
- **Caching** (`0x01-caching`): implemented FIFO, LIFO, LRU, MRU, LFU cache
  classes with eviction logic on a common `BaseCaching` interface.
- **i18n** (`0x02-i18n`): Flask + Flask-Babel multi-language (en/fr) app with
  locale selector, translations, mock user locales/timezones.
- **Queuing in JS** (`0x03-queuing_system_in_js`): Redis client + Kue queue in
  Node (only task 0 present — partial).

## JavaScript/Node track — `/home/alaabadawii/ALX/alx-backend-javascript/`
- ES6 features, Promises, classes, data manipulation (Set/Map/TypedArray/WeakMap).
- TypeScript + webpack (`0x04-TypeScript`).
- Node HTTP + Express servers incl. a `full_server/` with
  AppController/StudentsController/routes and a data CSV (`0x05-Node_JS_basic`).
- Unit & integration testing with Mocha/Chai/Sinon; API integration tests hitting
  `http://localhost:7865` (`0x06-unittests_in_js`).

## Advanced Python — `/home/alaabadawii/ALX/alx-backend-python/`
- Type annotations (`0x00`).
- `asyncio`: coroutines, concurrent tasks with `asyncio.gather`, async
  comprehensions (`0x01`, `0x02`).
- Unit + integration tests with `unittest.mock` (`0x03`).

## Storage — `/home/alaabadawii/ALX/alx-backend-storage/`
- **Advanced MySQL** (`0x00-MySQL_Advanced`): triggers, stored procedures,
  functions, views, indexes (sample `metal_bands.sql` dataset).
- **NoSQL / MongoDB** (`0x01-NoSQL`): mongo shell scripts + PyMongo programs,
  incl. Nginx log aggregation (`12-log_stats.py`).
- **Redis** (`0x02-redis_basic`): `Cache` class with `count_calls`/`call_history`
  decorators + a web URL-caching example with expiry and hit counters.

## User data & auth — `/home/alaabadawii/ALX/alx-backend-user-data/`
- PII protection / log redaction with `logging` + regex (`filtered_logger.py`),
  bcrypt password hashing.
- **Basic Auth** Flask API (`0x01`): base64 header extraction/decoding, user
  search.
- **Session Auth** (`0x02`): cookie/session creation & destruction.
- **Full auth service** (`0x03`): Flask + SQLAlchemy + bcrypt end-to-end
  (`/users`, `/sessions`, `/profile`, `/reset_password`).

## DevOps / SysAdmin — `/home/alaabadawii/ALX/alx-system_engineering-devops/`
- Shell scripting: basics, permissions, redirections, variables, loops, parsing,
  regex (Ruby oniguruma).
- Processes & signals; networking basics (OSI, TCP/UDP, DNS).
- Web infrastructure design documents (load balancer, firewall, SSL, SPOF,
  monitoring, primary/replica DB) — written design, no code (`0x09`).
- Configuration management with Puppet manifests (file/package/exec).
- SSH key management; Nginx installation and config; load balancing
  (X-Served-By header, HAproxy); HTTPS/SSL (DNS `dig`); web stack debugging
  (Apache/Nginx, strace, Puppet) across several projects.
- REST APIs with `requests` (JSONPlaceholder CSV/JSON export; Reddit API
  recursive pagination).
- Datadog monitoring setup (setup-only) and a written postmortem of an
  Apache 500 / `'phpp'` typo incident.
- Application server config: Nginx reverse proxy to a Python app server.

## Technologies
Python 3, Flask, Flask-Babel, SQLAlchemy, MySQL, MongoDB, Redis, Node.js, Express,
TypeScript, Puppet, Nginx, Bash, Datadog, Mocha/Chai/Sinon, asyncio.

## Concepts practiced
Pagination/hypermedia, cache eviction policies, i18n, background queues, REST
consumption, unit/integration testing, async I/O, advanced SQL, NoSQL, Redis
caching, authentication schemes, system administration, debugging, monitoring.

## Reported skill level (accurate)
Broad, hands-on practice across the backend/DevOps spectrum at curriculum level.
Queue task (`0x03`) is partial; monitoring was setup-only. Design documents are
written not implemented.

## Evidence / key files
`/home/alaabadawii/ALX/alx-backend/0x01-caching/`
`/home/alaabadawii/ALX/alx-backend/0x00-pagination/`
`/home/alaabadawii/ALX/alx-backend-storage/0x02-redis_basic/exercise.py`
`/home/alaabadawii/ALX/alx-backend-user-data/0x03-user_authentication_service/app.py`
`/home/alaabadawii/ALX/alx-backend-javascript/0x06-unittests_in_js/`
`/home/alaabadawii/ALX/alx-system_engineering-devops/0x19-postmortem/README.md`