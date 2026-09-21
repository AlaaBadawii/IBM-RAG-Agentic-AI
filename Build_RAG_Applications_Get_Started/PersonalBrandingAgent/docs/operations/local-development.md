# Local Development

How to run, test, and configure the **Personal Branding Agent** locally. This
document records the configuration-authority decision required by `PLAN.md` §8,
Step 0.

Environment setup itself lives in [`environment.md`](environment.md). This
document assumes `.venv` already exists.

---

## 1. Configuration authority

There are two configuration modules in the repository. **One is authoritative
and one is a compatibility shim.**

| Module | Role | Consumers |
|---|---|---|
| `app/config.py` | **Authoritative.** The single source of configuration. | all of `app/`, the tests |
| `config.py` (root) | Compatibility shim. Re-exports names from `app.config`. | **none** |

### The decision

**`app/config.py` is the authoritative configuration module.** Every application
module reads configuration from it. New configuration keys are added there and
nowhere else.

**Root `config.py` is retained, not deleted, and must not be used.** It is a
28-line re-export shim carrying the docstring *"Backwards-compatible re-export
of `app.config`."* It has **no consumers** — no module in `app/`, `tests/`, or
`Auth_handling/` imports it. It exists only so that an external reference to
`config.<NAME>` from the project root continues to resolve.

**Removal is a follow-up, not part of Step 0.** `PLAN.md` §8, Step 0 explicitly
scopes the root module out: *"Root `config.py` is **not** deleted in this
step."* Removing it changes the public import surface, which is a separate
decision requiring evidence that nothing outside the repository depends on it.
Until then it stays, and it stays unused.

### Practical consequence

```python
from app.config import TOP_K          # correct
import config                          # do not add new uses
```

When you add a setting, add it to `app/config.py`. Do not add it to both.

---

## 2. Configuration is environment-driven and CWD-independent

`app/config.py` loads `.env` from the **project root**, resolved from
`app/paths.py`, not from the current working directory:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

This means `.env` is found regardless of where you invoke Python from, and a
stray `.env` in an unrelated directory can never be picked up by accident.

`.env` is gitignored. It is **not** created by the reproduction procedure and is
not required for the test suite. See [`security.md`](security.md) for what
belongs in it and what must never be committed.

### Path resolution

All operational paths are absolute and derived from `PROJECT_ROOT`:

| Constant | Resolves to |
|---|---|
| `DATA_DIR` | `<PROJECT_ROOT>/data` — the knowledge base |
| `CHROMA_DIR` | `<PROJECT_ROOT>/chroma_db` — the vector store |
| `LOG_DIR` | `<PROJECT_ROOT>/logs` |
| `GOLD_QUERIES_PATH` | the retrieval evaluation gold set |

`tests/test_paths.py` covers this, including
`test_paths_independent_of_cwd`, which shells out from a temporary directory and
asserts the resolved paths are unchanged.

---

## 3. Running the tests

Always run from the project root:

```bash
cd <PROJECT_ROOT>
.venv/bin/python -m pytest tests/ -q
```

```text
79 passed
```

The suite is **fully offline and deterministic**. `tests/conftest.py` supplies
`FakeEmbeddings` (deterministic md5-bucket vectors) and `FakeCrossEncoder`
(deterministic token-overlap scoring), so no model is downloaded, no network call
is made, and no API key is needed.

Useful subsets:

```bash
.venv/bin/python -m pytest tests/test_retrieval.py -q      # retrieval layer
.venv/bin/python -m pytest tests/test_ingestion.py -q      # ingestion pipeline
.venv/bin/python -m pytest tests/ --collect-only -q        # confirm 79 collected
```

### Environment isolation

The suite must pass with the shared user site disabled. This is a standing
check, not a one-off — it proves the result comes from `.venv` alone:

```bash
PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/ -q
```

---

## 4. Running the CLIs

Three command-line entry points exist.

| CLI | Purpose |
|---|---|
| `python -m app.ingestion.pipeline` | Synchronize `data/` into the Chroma store |
| `python -m app.retrieval.compare "<question>"` | Run one question through all six retrieval strategies side by side |
| `python -m app.retrieval.evaluation` | Score all six strategies against the gold query set |

### From the project root

Nothing extra is needed — `-m` places the current directory on `sys.path`:

```bash
cd <PROJECT_ROOT>
.venv/bin/python -m app.ingestion.pipeline
.venv/bin/python -m app.retrieval.compare "What did I build with RAG?" --top-k 3
.venv/bin/python -m app.retrieval.evaluation
```

### From an unrelated working directory

The repository declares **no installable package** — there is no
`pyproject.toml`, `setup.py`, or `setup.cfg`, and `.venv` contains no `.pth` or
editable install pointing at the project. `python -m` searches the *current*
directory, so from elsewhere the module is simply not found:

```text
$ cd /tmp
$ <PROJECT_ROOT>/.venv/bin/python -m app.ingestion.pipeline
ModuleNotFoundError: No module named 'app'
```

That is an **import-path** concern, and `PYTHONPATH` is the correct way to solve
it. Set it to the project root:

```bash
cd /tmp
PROJECT_ROOT=/path/to/PersonalBrandingAgent

PYTHONPATH="$PROJECT_ROOT" "$PROJECT_ROOT/.venv/bin/python" \
    -m app.ingestion.pipeline

PYTHONPATH="$PROJECT_ROOT" "$PROJECT_ROOT/.venv/bin/python" \
    -m app.retrieval.compare "What did I build with RAG?" --top-k 3

PYTHONPATH="$PROJECT_ROOT" "$PROJECT_ROOT/.venv/bin/python" \
    -m app.retrieval.evaluation
```

All three were verified this way on 2026-09-22 from `/tmp`.

> **This is distinct from CWD-independence of the application's own state.**
> Once the module is importable, `.env`, `data/`, `chroma_db/`, and `logs/` are
> resolved from `PROJECT_ROOT` — never from the working directory. Confirmed by
> running the ingestion CLI from `/tmp` and reading its report:
>
> ```text
> store location : <PROJECT_ROOT>/chroma_db
> ```
>
> The absolute path comes from `app/paths.py`, not from the shell.

`PYTHONPATH` is a workaround for the absence of packaging, not the intended
long-term interface. Anything that schedules these CLIs (Step 12) must set it,
or run from the project root.

---

## 5. Ingestion is idempotent

`app/ingestion/pipeline.py` is content-hash driven: each chunk id is derived from
the source's content hash, so re-ingesting an unchanged corpus writes nothing.
Verified end to end on 2026-09-22 — two consecutive runs from `/tmp` produced
identical reports:

```text
files discovered : 71      files added   : 0
files unchanged  : 71      files updated : 0
files removed    : 0       chunks added  : 0
                           chunks removed: 0
total in store   : 342
```

A re-run is a no-op. Editing a source updates only that source's chunks; deleting
one removes its chunks. `chroma_db/` is gitignored, derived, and rebuildable
from `data/`.

---

## 6. Observed configuration condition

**The `.env` LLM key does not match the configured provider.** `app/config.py`
reads a key into `OPENROUTER_API_KEY` (accepting `OPENROUTER_API_KEY` or
`OPENAI_API_KEY`) and sends it to `OPENROUTER_BASE_URL`
(`https://openrouter.ai/api/v1`). The value currently in `.env` is an **OpenAI
platform key** (the `sk-proj-` family), not an OpenRouter key (the `sk-or-v1-`
family), so OpenRouter rejects it with `401 Missing Authentication header`.

This is **not caused by Step 0 and does not block it**. It does not affect
ingestion, vector search, metadata filtering, BM25, hybrid fusion, or reranking —
none of which need an LLM. Only the multi-query *expansion* step uses one, and it
degrades safely: it logs a warning, falls back to the original query, and the
CLI exits successfully. The evaluation CLI reports this as `fallbacks`, and all
12 gold queries showed the fallback path.

Consequence for the retrieval baseline: **`multi_query` currently scores
identically to plain `vector` search**, because expansion never happens. That is
expected under a misconfigured key, not a retrieval defect. The key must be
corrected before Step 8 (grounded post generation), which genuinely requires an
LLM. It is recorded as a known issue in
[`../implementation-status.md`](../implementation-status.md).

---

## 7. Related

| Document | Role |
|---|---|
| [`environment.md`](environment.md) | Python version, reproduction procedure, resolved versions |
| [`security.md`](security.md) | Secret vs non-secret split, redaction, gitignore boundary |
| [`../architecture/rag-architecture.md`](../architecture/rag-architecture.md) | Ingestion and retrieval design |
| [`../retrieval/`](../retrieval/) | The six retrieval strategies and measured results |
