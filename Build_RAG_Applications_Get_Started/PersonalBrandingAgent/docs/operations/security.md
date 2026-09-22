# Security

The secret boundary for the **Personal Branding Agent**: what is secret, what is
ordinary configuration, where each lives, and what prevents a secret from
reaching a log line or a commit. This document records the secret/non-secret
split required by `PLAN.md` §8, Step 0.

---

## 1. The rule

```text
A secret is a value that grants access to an external system on the user's behalf.
Secrets live only in .env (gitignored) or in a gitignored token file.
Everything else is ordinary configuration and is committable.
```

Nothing in this repository is encrypted, and no secret is committed in any form.
There is no secret-scanning tool and no key vault — the boundary is enforced by
`.gitignore`, by the redaction filter, and by the discipline described below.

---

## 2. The split

### Secrets — never logged, never committed

| Setting | What it is | Where it lives |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter key for the LLM used by multi-query expansion and (later) post generation | `.env` |
| `OPENAI_API_KEY` | Accepted alias for the same key — see §3 | `.env` |
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth application identifier | `.env` |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth application secret | `.env` |
| LinkedIn tokens | `access_token`, `id_token`, expiry, and scope returned by the OAuth exchange | `Auth_handling/linkedin_tokens.json` |

`.env` currently defines exactly three keys:

```text
OPENAI_API_KEY
LINKEDIN_CLIENT_ID
LINKEDIN_CLIENT_SECRET
```

The LinkedIn token file is written by the OAuth setup script and read by the
publishing scripts. It is **not** in `.env`, and it is gitignored separately
because it is produced at runtime rather than authored by hand.

> **Note on key type.** The LLM key is sent to `OPENROUTER_BASE_URL`
> (`https://openrouter.ai/api/v1`), so its *value* must be an OpenRouter key
> (`sk-or-v1-…`), not an OpenAI platform key (`sk-proj-…`). The setting **name**
> `OPENAI_API_KEY` is historical — see §3 — but the **provider** is OpenRouter.
> The key currently configured is of the OpenAI family and is therefore rejected
> by OpenRouter; this is recorded in
> [`local-development.md`](local-development.md) §6 and in
> [`../implementation-status.md`](../implementation-status.md). It affects only
> the LLM-dependent features, not ingestion or retrieval.

### Ordinary configuration — committable

None of the following is sensitive. All of it is safe to commit, and all of it
belongs in source control rather than in `.env`:

| Setting | Example | Where it lives |
|---|---|---|
| `MODEL_ID` | `deepseek/deepseek-v4-flash` | `app/config.py` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | `app/config.py` |
| `GENERATION_PARAMS` | `max_tokens`, `temperature` | `app/config.py` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | `app/config.py` |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `app/config.py` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | `1000`, `200` | `app/config.py` |
| `TOP_K`, `HYBRID_CANDIDATES`, `RRF_K`, `MULTI_QUERY_COUNT` | `5`, `10`, `60`, `4` | `app/config.py` |
| `EXCLUDE_READMES` | `True` | `app/config.py` |
| Filesystem paths | `<PROJECT_ROOT>/data`, `…/chroma_db`, `…/logs` | `app/paths.py` |

**The test is not "is it in `.env`" but "does it grant access to something".**
A model id, a chunk size, or a collection name grants nothing. The distinction
is what keeps the autonomous workflows of Steps 11–12 safe to schedule from an
environment file that is never committed.

### Runtime state — gitignored, not secret

| Path | Why it is excluded | Rebuildable? |
|---|---|---|
| `chroma_db/` | Derived vector store | **Yes** — re-ingest from `data/` |
| `state_db/` | Operational state: runs, publish intents, publications, failures, notifications, locks | **No** — authoritative |
| `logs/` | Log files; may contain operational detail | No, and not needed |
| `.venv/` | Local environment | Yes — from `requirements.txt` |
| `__pycache__/`, `*.pyc`, `.pytest_cache/` | Build artifacts | Yes |

None of these are excluded because they are confidential. `logs/` is excluded
partly *because* log content is one of the places a secret could leak into —
see §4.

**The distinction that matters is rebuildability, not confidentiality.**
`chroma_db/` can be thrown away and recreated from `data/`. `state_db/` cannot:
it holds the local publication history, which is authoritative precisely
because LinkedIn does not grant the read access that would allow it to be
reconstructed (`PLAN.md` §5.1). Deleting `state_db/` loses the record of what
was published and the write-ahead intents that prevent publishing it twice.
It is gitignored so it does not enter source control — not so it can be
discarded.

---

## 3. Why `OPENAI_API_KEY` also works

`app/config.py` reads:

```python
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
```

`OPENROUTER_API_KEY` is tried first and `OPENAI_API_KEY` is the accepted
fallback. The alias exists because the LLM client is `langchain_openai`'s
`ChatOpenAI`, which reads `OPENAI_API_KEY` by convention, and because the `.env`
in this repository was authored under the older name. The module docstring
records the reasoning explicitly: *"It is the OpenRouter key — the name is
historical."*

Both names are treated as secrets by the redaction filter, so a value under
either name is scrubbed from logs.

---

## 4. Secret redaction in logs

`app/logging_config.py` installs a `logging.Filter` that removes secret values
before any handler sees them.

The filter operates on the **secret's value, not its variable name**:

```python
class SecretRedactionFilter(logging.Filter):
    def __init__(self):
        self._secrets = [v for v in (
            os.getenv("OPENAI_API_KEY"),
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv("LINKEDIN_CLIENT_ID"),
            os.getenv("LINKEDIN_CLIENT_SECRET"),
        ) if v]
```

This matters: a secret interpolated into a message — `logger.info(f"using {key}")`
— is still caught, because the filter scans the rendered message text and
replaces any occurrence of a known secret value with `[REDACTED]`. Matching on
variable names would not catch that case.

Coverage:

- `get_logger(name)` attaches the filter to a named logger, idempotently.
- `setup_logging()` attaches it to the **root logger**, so every handler —
  console (`stderr`) and `logs/app.log` — sees redacted records.

### What redaction does not cover

- The filter runs at log time. A secret written directly to a file, printed with
  `print()`, or emitted by a third-party library that configures its own logging
  without passing through these loggers is **not** covered.
- The LinkedIn token file's *contents* are not registered as secrets — only
  `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` are. A token value echoed to
  a log would rely on the token file being read through controlled paths
  (`PLAN.md` Step 5 hardens this).

---

## 5. The commit boundary

`.gitignore` is the enforcement point. Verified on 2026-09-22 with
`git check-ignore -v`:

```text
.env                                 → .gitignore:1:.env
Auth_handling/linkedin_tokens.json   → .gitignore:2:…
chroma_db/                           → .gitignore:3:chroma_db/
state_db/                            → .gitignore:4:state_db/
__pycache__/, *.pyc                  → .gitignore:5-6
.pytest_cache/                       → .gitignore:7
.venv/                               → .gitignore:9:.venv/
logs/                                → .gitignore:10:logs/
```

Before committing anything that touches configuration, confirm the boundary still
holds:

```bash
git status --short          # .env must never appear
git check-ignore -v .env    # must print a matching rule
```

### Rules for adding configuration

1. **A new secret goes in `.env` and in the redaction filter** — add the variable
   name to the `SecretRedactionFilter.__init__` tuple so its value is scrubbed
   from logs.
2. **A new non-secret setting goes in `app/config.py`** with a sensible default,
   and is committed. It does not belong in `.env`.
3. **Never add a secret to `app/config.py`,** even with an empty default that
   "should" be overridden. A default is a committed value.
4. **Never widen `.gitignore`** to un-ignore a file under `.env`, the token file,
   `chroma_db/`, or `logs/` to make something commit — that is a signal the thing
   being committed is in the wrong place.

| `SMTP_PASSWORD` | Gmail app password for failure notifications | `.env` |
| `SMTP_USERNAME` | Gmail address used as the SMTP login | `.env` |

`SMTP_HOST/PORT/SENDER/RECIPIENT/TLS/TIMEOUT` are ordinary configuration
(committable defaults in `app/config.py`; addresses go in `.env` because
they are the user's, not because they are secret). Only the password grants
access, so only it is in the redaction list — recorded notification rows
carry `host:port tls=mode`, never credentials or message bodies.

### What must never appear in logs, tests, or documentation

Real credential values of any kind: API keys, app passwords, OAuth client
secrets, access/refresh/id tokens, or full token-file contents. Tests use
obviously-fake values (`fake-access-token-value`); documentation names
variables and key *families* (`sk-or-v1-…` vs `sk-proj-…`) but never values.
A `tests/test_operations_docs.py` check fails the suite if real key material
patterns appear under `docs/`.

### Boundaries this document does not cover alone

- **PID-based lock ownership** (`docs/operations/scheduling.md` §3): lock
  owners embed `hostname:pid:token`. A pid is process-table data, not a
  secret — but treat rejection rows as operational detail, not public text.
- **Manual intervention** (`docs/operations/recovery.md`, `PLAN.md` §11):
  ambiguity resolution, re-authorization, and lock clearing are human acts
  with named procedures. Automation must never perform them silently.

---

## 6. Related

| Document | Role |
|---|---|
| [`environment.md`](environment.md) | Environment definition and reproduction |
| [`local-development.md`](local-development.md) | Configuration authority and CLI usage |
| [`../architecture/linkedin-integration.md`](../architecture/linkedin-integration.md) | OAuth scopes, tokens, and publishing |
| `PLAN.md` §5.1, Step 5 | LinkedIn permission limits and token lifecycle |
| `PLAN.md` Step 7 | Notification credentials (SMTP) |
