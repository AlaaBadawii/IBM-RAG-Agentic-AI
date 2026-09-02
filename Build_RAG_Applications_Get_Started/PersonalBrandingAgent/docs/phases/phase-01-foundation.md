# Phase 1 — Foundation

## Goal

Create the technical foundation of the Agent: package structure, configuration,
environment handling, dependency management, logging, error handling, secrets,
security basics, testing foundation, path handling, and the application
entrypoint.

## Why This Phase Exists

Every later phase depends on a stable, testable, secure base. The current repo
has `config.py`, `requirements.txt`, `.env`, and `.gitignore` but no `app/`
package, no logging/error strategy, and no tests. This phase establishes the
boundaries every other component builds on.

## Inputs

- Existing `config.py` (env loading, model id, gen params, embedding model,
  Chroma dir, chunk params)
- Existing `requirements.txt`
- Existing `.env` / `.env.example` / `.gitignore`
- Existing `Auth_handling/` (unused by this phase; secured only)

## Outputs

- An `app/` package with a clear internal layout
- Centralized configuration and paths
- Logging setup
- Error handling helpers and a custom exception hierarchy
- Secrets protection (`.env` not committed, credentials never logged)
- A minimal test harness (`pytest`)
- An application entrypoint
- Updated `.gitignore` / `requirements.txt` as needed

## Architecture

```text
app/
config/
tests/
docs/
data/
Auth_handling/
```

Establish clear boundaries between:

```text
configuration
application
knowledge
integrations
tests
```

Target layout introduced by this phase (only the files this phase needs):

```text
app/
├── __init__.py
├── config.py            # moves central config into the package
├── logging_config.py    # logging setup
├── errors.py            # exception hierarchy
└── paths.py             # path handling (data/, chroma_db/, etc.)
tests/
├── conftest.py
├── test_config.py
└── test_paths.py
```

The phase must explicitly protect:

```text
.env
linkedin_tokens.json
API keys
OAuth secrets
Chroma persistence
```

Credentials stay outside source control.

## Files Introduced

- `app/__init__.py`
- `app/config.py` (refactor of the root `config.py`)
- `app/logging_config.py`
- `app/errors.py`
- `app/paths.py`
- `tests/conftest.py`
- `tests/test_config.py`
- `tests/test_paths.py`
- `.env.example` (updated as needed)
- `.gitignore` (updated as needed)

> The root `config.py` may be kept as a thin re-export for backwards
> compatibility, or its contents moved into `app/config.py`. Choose one and be
> consistent.

## Implementation Tasks

1. Create the `app/` package and `tests/` package with `__init__.py` files.
2. Move/centralize configuration into `app/config.py`; load all values from the
   environment via `python-dotenv`; fail fast with a clear message if required
   secrets are missing (in a configurable way so local dev without LinkedIn is
   still possible).
3. Implement `app/paths.py` with absolute, canonical paths for `data/`,
   `chroma_db/`, templates, and any other runtime directories. Avoid
   working-directory-dependent relative paths.
4. Implement `app/logging_config.py` with a structured, configurable logger.
   **Never log secrets or tokens.**
5. Implement `app/errors.py` with a small exception hierarchy (e.g.,
   `AgentError`, `ConfigError`, `IngestionError`, `RetrievalError`,
   `GenerationError`, `EvaluationError`, `LinkedInError`).
6. Update `requirements.txt` with the packages needed for foundation and
   testing (`pytest`).
7. Update `.gitignore` to cover `.env`, `Auth_handling/linkedin_tokens.json`,
   `chroma_db/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.venv/`.
8. Add an application entrypoint (CLI stub that will be wired to the Agent in
   later phases).

## Tests

- `tests/test_config.py` — env-derived config loads correctly; missing required
  values raise `ConfigError` (using monkeypatched env).
- `tests/test_paths.py` — paths are absolute and point to the intended
  directories.
- A logging test verifying that secret values are redacted / not emitted.

Do not make tests depend on real API keys or network access.

## Acceptance Criteria

- `app/` package imports cleanly.
- `pytest` runs with at least the foundation tests passing.
- Running the app/CLI entrypoint produces a logged startup message and no
  crash.
- No secret (API key, token, client id/secret) appears in any log output or in
  source control.
- `git status` shows credentials and `chroma_db/` ignored.

## Failure Modes

- **Missing env vars** → clear `ConfigError` with actionable message; do not
  silently default to empty secrets.
- **Broken paths** → paths module fails early and predictably; log the resolved
  path on error.
- **Secrets leaked in logs** → redaction rule; a test guards against it.

## Security Considerations

- `.env` and `Auth_handling/linkedin_tokens.json` remain untracked.
- Logging never includes secrets; the logging config includes a sanitizer.
- Config loading distinguishes required vs optional values.
- Keep dependency pins documented; use a venv.

## Dependencies on Previous Phases

None (first phase). Reuses the existing `config.py` and `requirements.txt`.

## Future Extensions

- Centralized feature flags / environment profiles (dev vs prod).
- Telemetry hooks to be consumed in Phase 10 (observability).
- Config schema validation (e.g., pydantic) as the config grows.

## Course Alignment

- Flask app structure and `config.py` pattern map to the IBM course labs.
- Introduces the discipline of a package layout and tests before model work.

## Checklist

- [ ] `app/` package created with configuration, logging, errors, paths
- [ ] Root `config.py` refactored or re-exported consistently
- [ ] Logging configured with secret sanitization
- [ ] Exception hierarchy defined
- [ ] `requirements.txt` includes `pytest`
- [ ] `.gitignore` covers all secret/persistent/local artifacts
- [ ] Entrypoint runs and logs startup
- [ ] `pytest` passes foundation tests
- [ ] `git status` confirms credentials and `chroma_db/` ignored