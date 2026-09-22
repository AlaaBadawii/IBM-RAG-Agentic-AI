# Scheduling, Locks & Recovery

How the two workflows run unattended (`PLAN.md` §8, Step 12). There is **no
long-running Python scheduler** — an OS trigger runs a one-shot entry point,
which exits with the workflow's status.

---

## 1. The trigger: cron

`ops/personal-branding-agent.cron` holds the whole schedule:

| Workflow | Schedule | Command |
|---|---|---|
| branding | every 8h (`0 */8 * * *`) | `python -m app.workflows.branding` |
| sync | daily 02:10 (`10 2 * * *`) | `python -m app.workflows.sync` |

Install:

```bash
# Set PROJECT_ROOT at the top of ops/personal-branding-agent.cron first.
crontab ops/personal-branding-agent.cron
```

Each line `cd`s into the checkout (the repository declares no installable
package, so `python -m` resolves from the working directory — see
[`local-development.md`](local-development.md) §4) and appends output to the
gitignored `logs/` directory. No exit-masking constructs may be added: the
scheduler passes the workflow exit status straight through.

### Why cron, not a systemd timer

One user, one machine, fixed coarse intervals. That needs a trigger, not an
init integration: cron is one file with no daemon-reload, no lingering, and
no dependency on a running systemd init. A systemd timer would add two
services plus two timers for zero functional gain here. Revisit if
sub-minute granularity, unit dependencies, or journal integration become
requirements.

### Exit codes (the scheduler's interface)

| Code | Meaning |
|---|---|
| `0` | success — including a run that published nothing, or one post |
| `1` | `WORKFLOW_FAILED` — a phase could not complete; notified once |
| `2` | `REQUIRES_HUMAN_INTERVENTION` — notified once, never retried |
| `3` | locked out — the workflow was already running; rejected without running |

---

## 2. Overlap protection

Each workflow owns one row in the Step 1 `locks` table (`workflow:sync`,
`workflow:branding`), taken before the run starts and released afterwards —
and only by the invocation that took it. A second invocation while the lock
is held records the rejection and exits `3` without entering the workflow.
No scheduler is involved: calling `run_sync()` / `run_branding()` directly
is guarded the same way.

## 3. Stale-lock recovery

A lock left behind by a crash (`SIGKILL`, power loss, `store` failure) is
reclaimed automatically by the next invocation — but **never on timeout
alone**. Every owner this layer writes is `hostname:pid:token`, and an
expired lock whose pid is still alive on this host is treated as held: the
new invocation is rejected rather than granted, so a run that merely overran
its TTL can never gain a concurrent twin. Only an expired lock whose owner
process is demonstrably gone is reclaimed, through the atomic Step 1
transaction, so two simultaneous recovery attempts cannot both win. Every
recovery is recorded in operational state and logged.

One honest edge: pid reuse. If a dead owner's pid has been recycled by an
unrelated long-lived process, the lock looks live and ticks keep being
rejected — a missed run, never an overlap. It self-heals when that pid dies;
the rejection rows name the squatting pid so an operator can clear the row.

## 4. Interrupted runs

After acquiring the lock, the invocation reports any still-unfinished run of
the same workflow (one occurrence-counted row each) and leaves it untouched:
never finished, never retried. An unfinished run seen while the lock is held
is the live holder's own run in progress, so it is *not* reported. Recovery
never touches publish state, so an ambiguous publication cannot be retried
by this path — the branding workflow's own pre-publish guard still applies.

---

## 5. Manual operation

```bash
cd <PROJECT_ROOT>
.venv/bin/python -m app.workflows.sync        # guarded sync, once
.venv/bin/python -m app.workflows.branding    # guarded branding, once
```

Useful state queries (all read-only):

```bash
# unfinished (possibly interrupted) runs
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for r in s.list_unfinished_runs(): print(r.run_id, r.workflow, r.started_at)"
```

Clearing a lock by hand is almost never needed (stale recovery is
automatic). If pid-reuse keeps an invocation out and the squatter is known
to be unrelated, delete that workflow's `locks` row — the next tick takes it
fresh. Never delete a lock held by a live workflow process.
