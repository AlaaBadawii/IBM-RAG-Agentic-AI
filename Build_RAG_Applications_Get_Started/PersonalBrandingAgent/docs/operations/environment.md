# Environment

How the **Personal Branding Agent** runtime environment is defined, reproduced,
and verified. This document is the authoritative description of the local
development environment. It was produced by `PLAN.md` §8, Step 0.

```text
Status      : verified on 2026-09-22
Mechanism   : project-local Python venv (stdlib `venv`)
Python      : 3.10.12
Dependency  : requirements.txt (repository root, unmodified)
```

---

## 1. The decision

**The project runs in a project-local `.venv` on Python 3.10, installed from the
existing `requirements.txt`.**

No other environment mechanism is used. `uv`, Poetry, Conda, Docker, and
virtualenv are all deliberately **not** introduced — there is no repository
evidence justifying them. This matches `PLAN.md` §12.1 decision 6.

---

## 2. Why Python 3.10 — repository evidence

The version is not a preference. It is the version the pinned stack requires and
the version already present on the machine.

**a. The resolved stack's floor is 3.10.** Every pinned major dependency
declares `>=3.10` in its published metadata. The floor is set by `torch` and the
LangChain 1.x core:

| Package | Resolved | Declared `Requires-Python` |
|---|---|---|
| `langchain` | 1.4.2 | `<4.0.0,>=3.10.0` |
| `langchain-core` | 1.6.4 | `<4.0.0,>=3.10.0` |
| `torch` | 2.14.0 | `>=3.10` |
| `sentence-transformers` | 5.7.0 | `>=3.10` |
| `transformers` | 5.17.0 | `>=3.10.0` |
| `pytest` | 9.1.1 | `>=3.10` |
| `numpy` | 2.2.6 | `>=3.10` |
| `onnxruntime` | 1.23.2 | `>=3.10` |
| `tokenizers` | 0.23.2 | `>=3.10` |

Python 3.9 is therefore **impossible** with these pins. 3.10 is the lowest
version that satisfies the whole set.

**b. The application source is 3.10-compatible and needs nothing newer.** `app/`
uses PEP 604 unions (`str | None`) and PEP 585 builtin generics (`list[str]`),
both available in 3.10. A scan of `app/` and `tests/` finds **no** Python 3.11+
only syntax (`tomllib`, `except*`, `enum.StrEnum`, `datetime.UTC`, `typing.Self`).

**c. No upper bound is declared anywhere.** There is no `pyproject.toml`,
`setup.py`, or `setup.cfg` in the repository, and no `requires-python` /
`python_requires` declaration in any source file. The environment mechanism is
whatever `requirements.txt` resolves to.

**d. The machine's system interpreter is already 3.10.12** (`/usr/bin/python3.10`,
`/usr/bin/python3`), which is the baseline the retrieval layer was built and
tested against. `requirements.txt` records "installed versions verified
2026-09-08" against that baseline.

**Conclusion:** Python 3.10 is the intended version. It is the floor of the
pinned stack, it is what the retrieval layer was verified against, and it is
what the machine provides.

---

## 3. Reproduction procedure

From a clean checkout on a machine with Python 3.10:

```bash
# 1. Create the project-local environment.
python3.10 -m venv .venv

# 2. Bring the packaging toolchain up to date.
.venv/bin/python -m pip install --upgrade pip

# 3. Install the pinned stack.
.venv/bin/python -m pip install -r requirements.txt

# 4. Confirm the pins are mutually consistent.
.venv/bin/python -m pip check

# 5. Confirm the baseline.
.venv/bin/python -m pytest tests/ -q
```

This procedure requires **no manual patching, no pin edits, and no
workarounds**. It was executed twice: once to build `.venv`, and once into a
throwaway environment to prove it is repeatable.

`.venv/` is listed in `.gitignore` and is never committed.

### Expected result of step 5

```text
79 passed
```

79 tests across 7 modules. This is the recorded historical baseline.

---

## 4. Resolved versions

Recorded from `.venv` on **2026-09-22** (Python 3.10.12, pip 26.2.1).
`requirements.txt` pins ranges, not exact versions, so these are the versions
the ranges currently resolve to.

### Direct dependencies (as pinned in `requirements.txt`)

| Package | Pin | Resolved |
|---|---|---|
| `langchain` | `>=1.3,<2` | 1.4.2 |
| `langchain-core` | `>=1.6,<2` | 1.6.4 |
| `langchain-community` | `>=0.4,<1` | 0.4.2 |
| `langchain-openai` | `>=1.5,<2` | 1.6.3 |
| `langchain-chroma` | `>=1.1,<2` | 1.1.0 |
| `langchain-huggingface` | `>=1.2,<2` | 1.2.2 |
| `langchain-text-splitters` | `>=1.1,<2` | 1.1.2 |
| `chromadb` | `>=1.5,<2` | 1.5.9 |
| `sentence-transformers` | `>=5.7,<6` | 5.7.0 |
| `rank_bm25` | `>=0.2.2,<1` | 0.2.2 |
| `pydantic` | `>=2.13,<3` | 2.13.5 |
| `python-dotenv` | `>=1.2,<2` | 1.2.3 |
| `requests` | `>=2.34,<3` | 2.34.2 |
| `pytest` | `>=9.1,<10` | 9.1.1 |
| `Flask` | `>=3.0` | 3.1.3 |

**No pin was relaxed, and `requirements.txt` was not modified.** The historical
dependency conflict was not a defect in the pins — it was an environment that
did not match them.

### Notable transitive versions

| Package | Resolved |
|---|---|
| `torch` | 2.14.0 |
| `transformers` | 5.17.0 |
| `tokenizers` | 0.23.2 |
| `numpy` | 2.2.6 |
| `onnxruntime` | 1.23.2 |
| `openai` | 3.16.2 |
| `pip` | 26.2.1 |
| `setuptools` | 84.0.0 |
| `wheel` | 0.48.0 |

The full frozen list (158 distributions) is environment-local and deliberately
not committed — `requirements.txt` remains the single source of truth for what
to install.

---

## 5. Isolation from `~/.local`

The `.venv` must be the **only** source of packages. A shared `~/.local`
installation can silently satisfy an import that the pinned stack cannot, which
would make a broken environment look healthy.

Verified on 2026-09-22:

```text
sys.prefix                          <PROJECT_ROOT>/.venv
sys.base_prefix                     /usr
site.ENABLE_USER_SITE               False
paths containing ".local" in sys.path   NONE
```

`pyvenv.cfg` records `include-system-site-packages = false`.

Independently, the full suite was re-run with the user site explicitly disabled:

```bash
PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/ -q
→ 79 passed
```

Identical result. No package resolves out of `~/.local`.

---

## 6. Runtime data and the pre-existing store

`chroma_db/` is derived, regenerable runtime state. It is gitignored and is not
part of the environment definition.

The store present in the working tree was **built under `chromadb` 0.4.24** —
the version that caused the original breakage. Step 0 verified that it opens and
serves correctly under `chromadb` 1.5.9: ingestion found 71 sources and reported
all 71 unchanged, with 342 chunks in the store and no writes. No migration step
was needed. Should the store ever become unreadable it can be rebuilt from
`data/` by running the ingestion CLI; that is a recovery action, not a routine
one.

### Model caches

The two models the pipeline uses are resolved from the local Hugging Face cache:

```text
sentence-transformers/all-MiniLM-L6-v2      embeddings
cross-encoder/ms-marco-MiniLM-L-6-v2        reranking
```

Both are present in `~/.cache/huggingface/hub`. The cache is **not** part of the
repository and **not** part of `requirements.txt` — a machine without it will
download the models on first use and therefore needs network access once. The
test suite never needs them: `tests/conftest.py` supplies deterministic fakes
(`FakeEmbeddings`, `FakeCrossEncoder`) and runs fully offline.

---

## 7. Scope note

Step 0 changed **no application source code** and **no test**. It created an
environment, verified it, and wrote this documentation. Topics that belong to
later steps and are deliberately *not* covered here:

- Merging or removing the two configuration modules — see
  [`local-development.md`](local-development.md), and `PLAN.md` Steps 0/14.
- Adding new configuration keys — those arrive with the steps that need them.
- Scheduler, deployment, and secrets management — `PLAN.md` Steps 12 and 14.
