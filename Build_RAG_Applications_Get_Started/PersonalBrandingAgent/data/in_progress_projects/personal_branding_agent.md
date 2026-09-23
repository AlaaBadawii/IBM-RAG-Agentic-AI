# Personal Branding Agent — autonomous personal-branding system (Abu Prompt)

## Status
IN PROGRESS. The autonomous system described in `PLAN.md` is implemented
through Step 14: knowledge synchronization, branding context, generation,
verification, bounded Agent reasoning, persistent publishing, notifications,
workflows, and scheduling all exist as code under `app/`. The project is
approaching its first public introduction (see Launch milestone below). One
post has been published (2026-09-23, a certification post); the launch post
itself has not.

## Identity
- Name: **Abu Prompt**
- Handle: **@AbuPrompt**
- Arabic: **أبو برومبت**

This is the public identity of this system. Brand-facing detail lives in
`../public_positioning/abu_prompt.md`; this file records the engineering
facts.

## What it is
A personal-branding automation system built around Alaa's own technical
knowledge, projects, lessons, and evidence. It retrieves grounded personal
context from the `data/` corpus, evaluates content opportunities, reasons
about publish-worthiness, generates a candidate post, verifies it against
evidence through deterministic gates, and publishes to LinkedIn only when
every safeguard passes — otherwise it records `DO_NOT_PUBLISH`.

## What is actually implemented
All of the following exist as code in this repository:

- grounded personal context (`app/context/` — assembly, evidence hierarchy,
  coverage reporting, insufficient-evidence state)
- content-opportunity evaluation (`app/agent/reasoning.py`,
  `app/agent/prompt.py` — topic candidates from non-empty evidence sections)
- bounded Agent reasoning (`app/agent/agent.py` — one `BrandingAgent` proposing
  from retrieved evidence only; revision bound owned by verification)
- grounded post generation (`app/generation/` — LCEL chain from assembled
  context and selected evidence)
- deterministic evidence verification (`app/verification/` — authoritative
  gates plus advisory LLM assist; `revision_decision` owns PASS / REVISE /
  REJECT with a bound)
- safe/idempotent LinkedIn publishing (`app/publishing/` intent state machine
  plus `app/integrations/linkedin/` classified transport; at most one
  publication attempt per workflow run)
- persistent workflow state (`app/state/` — SQLite: runs, checkpoints,
  intents, publications, failures, notifications, locks)
- scheduled 8-hour branding workflow (`app/workflows/branding.py`, triggered
  by `ops/personal-branding-agent.cron` every 8 hours)
- incremental knowledge synchronization (`app/sync/` over the `sources.yaml`
  registry into the existing ingestion pipeline; checkpoints in the state
  store)
- failure notification and recovery safeguards (`app/notify/` SMTP service;
  `WORKFLOW_FAILED` / `REQUIRES_HUMAN_INTERVENTION` persisted with exactly one
  notification; overlap locks with stale-lock recovery)

## Normal flow
```text
knowledge/context
→ BrandingAgent
→ generation
→ verification
→ publishing safeguards
→ publish OR DO_NOT_PUBLISH
```

`DO_NOT_PUBLISH` is a successful workflow outcome, not a failure. No post is
required on any run; the system prefers no post over weak, repetitive,
unsupported, or low-value content.

## Launch milestone
The project is approaching its **first public introduction of Abu Prompt**.
Introducing the system itself — what it is, what it demonstrably does, and
what it deliberately does not do yet — is a meaningful potential publishing
opportunity the autonomous Agent may recognize from this context.

This records an opportunity, not an outcome: **the launch post itself has not
been published**, and nothing here instructs the Agent to publish. One post
has gone out since this was written — the 2026-09-23 certification post above,
published by a scheduled run. Whether any further post goes out remains the
Agent's decision under the normal flow above, subject to generation,
verification, and publishing safeguards.

## Planned, not implemented
`@AbuPrompt` mention-triggered responses are **planned, not implemented**.
No comment monitoring, reply logic, or mention handling exists in the system.

```text
No @AbuPrompt mention
→ ignore

@AbuPrompt without a meaningful question/request
→ ignore

@AbuPrompt + meaningful question/request
→ future system may consider responding
```

Any future response must use the same grounded-context → generation →
verification safety chain, as a separate reactive workflow — never mixed into
proactive publishing. See `PLAN.md` Step 14 and
`../public_positioning/abu_prompt.md` for the positioning half of this plan.

## Provenance
- `app/context/`, `app/agent/`, `app/generation/`, `app/verification/`
- `app/publishing/`, `app/integrations/linkedin/`, `app/state/`
- `app/workflows/branding.py`, `app/sync/`, `sources.yaml`
- `app/notify/`, `ops/personal-branding-agent.cron`
- `PLAN.md` Steps 0–14 (Step 14 names the `@AbuPrompt` future capability)
