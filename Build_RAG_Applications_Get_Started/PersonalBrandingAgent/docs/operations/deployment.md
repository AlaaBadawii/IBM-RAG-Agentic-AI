# Deployment & Reproduction

Reproduce a working system from a clean checkout using only this document
(`PLAN.md` Step 14: a clean checkout plus documentation reproduces a
working, scheduled system). Every command below is the actual repository
command. No step requires network access except the one-time `pip install`
and the one-time model download, both marked.

---

## 1. Python environment

Project-local virtualenv on Python 3.10, from the unmodified pins
(authoritative detail: [`environment.md`](environment.md)):

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt   # network, one time
.venv/bin/python -m pip check
```

No `uv`, Poetry, Conda, Docker, or system-site packages. Verify isolation:

```bash
PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/ -q
```

## 2. Configuration (`.env`)

Copy the template and fill values — names only; values are never committed,
logged, or documented:

```bash
cp .env.example .env
```

| Variable | Required for | Default when empty |
|---|---|---|
| `OPENROUTER_API_KEY` (or `OPENAI_API_KEY` alias) | LLM features: multi-query expansion, generation, advisory judge, Agent reasoning | Model calls fail closed with a `configuration` failure |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | OAuth setup + publishing | Publishing refuses as an authentication failure |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SENDER`, `SMTP_RECIPIENT` | Failure notifications | Runs record failures but cannot alert (recorded as delivery failures) |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP login (Gmail: app password) | Login skipped when `SMTP_USERNAME` is empty |
| `SMTP_TLS` (`starttls`\|`ssl`\|`none`), `SMTP_TIMEOUT_SECONDS`, `SMTP_REPEAT_AFTER_HOURS` | Transport + noise control | `starttls`, `30.0`, `24.0` |

Everything else is ordinary committed configuration in `app/config.py`
(model id, retrieval/chunking parameters, LinkedIn API version/timeouts,
paths). A first real branding run with unset keys reports
`REQUIRES_HUMAN_INTERVENTION` naming the variable — that is the designed
unconfigured behavior, not a defect (Known Issue #5).

## 3. State initialization and migrations

No manual step: the store is created on first use at
`state_db/operational_state.db` with foreign keys, WAL mode, and all
migrations applied. Verify:

```bash
.venv/bin/python -c "
from app.state import StateStore, SCHEMA_VERSION
with StateStore() as s:
    print('schema version:', s.schema_version, '(code expects', SCHEMA_VERSION + ')')"
```

Expected: `schema version: 4 (code expects 4)`. A newer store than the code,
or a gapped migration ledger, refuses to operate — that refusal is correct;
do not edit the ledger. `state_db/` is authoritative and not rebuildable
(deleting it loses publication history and duplicate protection); `chroma_db/`
is derived and rebuilds from `data/` via the ingestion CLI.

The first model download needs network once (Hugging Face cache); the test
suite never needs it (deterministic fakes).

## 4. Test execution

```bash
PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/ -q
```

Focused subsets:

```bash
.venv/bin/python -m pytest tests/test_autonomous_evaluation.py -q  # 18 scenarios + milestone
.venv/bin/python -m pytest tests/test_scheduling.py tests/test_workflows.py -q
.venv/bin/python -m pytest tests/test_operations_docs.py -q         # docs/scheduler/ADR consistency
```

## 5. Scheduler installation

Cron only — no daemon, no worker, no Python scheduler process:

```bash
# 1. Point PROJECT_ROOT at this checkout in ops/personal-branding-agent.cron
# 2. Install:
crontab ops/personal-branding-agent.cron
# 3. Confirm:
crontab -l
```

Result: branding every 8h (`0 */8 * * *`), sync daily at 02:10, output
appended to `logs/branding-cron.log` / `logs/sync-cron.log`, exit statuses
unmasked (`0` success · `1` failed · `2` needs a person · `3` locked out).
Full rationale and per-code meaning: [`scheduling.md`](scheduling.md).

## 6. Verification commands

```bash
# A guarded sync and branding pass, once each, foreground:
.venv/bin/python -m app.workflows.sync
.venv/bin/python -m app.workflows.branding
echo $?   # the workflow exit status, straight through

# Latest runs and their recorded outcomes:
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for r in s.list_runs(limit=5):
        print(r.run_id, r.workflow, r.outcome, r.failed_phase)"

# Commit boundary hygiene (secret check):
git status --short          # .env must never appear
git check-ignore -v .env Auth_handling/linkedin_tokens.json
```

## 7. Operational commands (daily use)

| Task | Command |
|---|---|
| Run sync once | `python -m app.workflows.sync` (from the project root) |
| Run branding once | `python -m app.workflows.branding` |
| Inspect unfinished runs | `StateStore().list_unfinished_runs()` (see `recovery.md` §1) |
| Inspect locks | `get_lock('workflow:sync' / 'workflow:branding')` (see `recovery.md` §2) |
| Review ambiguities | query `unknown_requires_review` publications (see `recovery.md` §3) |
| Verify credential without posting | `Auth_handling/test_credentials.py` |
| Publish one real post by hand | `Auth_handling/test_post.py` (interactive; see `../evaluation/manual-linkedin.md`) |
| Re-ingest the knowledge base | `python -m app.ingestion.pipeline` |
| Compare retrieval strategies | `python -m app.retrieval.compare "<question>"` |
| Score retrieval vs gold set | `python -m app.retrieval.evaluation` |

From another directory, prefix with `PYTHONPATH=<PROJECT_ROOT>`
([`local-development.md`](local-development.md) §4); application state
itself is always resolved from the project root, never the working
directory.

## 8. Related

| Document | Role |
|---|---|
| [`environment.md`](environment.md) | Python version evidence, resolved pins |
| [`local-development.md`](local-development.md) | Config authority, CLIs, idempotency |
| [`security.md`](security.md) | Secret boundary, redaction, gitignore |
| [`scheduling.md`](scheduling.md) | Trigger choice, locks, exit codes |
| [`recovery.md`](recovery.md) | Failure procedures |
| [`state-model.md`](state-model.md) | Schema being initialized above |
