# Publishing, Credentials & Notifications — Operator View

How posts leave the machine, how the credential lives and dies, and how the
operator hears about either (`PLAN.md` Steps 5–7, 11). Design rationale lives
in [`../architecture/linkedin-integration.md`](../architecture/linkedin-integration.md);
this document is the lifecycle-and-behavior reference for operating it.

---

## 1. Publishing lifecycle

Every post travels one path — `BrandingAgent` decision → Step 6
`PublishingService` → Step 5 `publish_to_linkedin` → LinkedIn — in this
order, with state written at each step:

```text
duplicate checks (exact · near · overuse — refused before anything is written)
  → write-ahead intent (durable BEFORE any request; one per run, DB-enforced)
  → mark attempt started (last write before the request)
  → LinkedIn request (bounded timeouts on every call)
  → record outcome from evidence:
      post id returned      → published
      definitive rejection  → failed (content releasable for later runs)
      timeout / no post id  → unknown_requires_review (never retried)
```

At-most-one-post-per-run is a database property
(`ux_publish_intents_run`), not workflow discipline. At most one
*unresolved* intent per content hash across runs
(`ux_publish_intents_unresolved_content`): a `failed` intent releases its
content; an `unknown_requires_review` one keeps blocking it.

Interrupted attempts resolve in opposite directions (`recover_run`):
`attempt_started` with no outcome → `unknown_requires_review` (a post may
exist — a person confirms); `intent_created` → `failed` (nothing was sent).

## 2. LinkedIn error classification (what the system does next)

| Category | Example | Retry? | Outcome |
|---|---|---|---|
| `authentication` (401, missing/unreadable/expired credential) | expired token | never — needs a person | `failed` + `REQUIRES_HUMAN_INTERVENTION` |
| `transport`, connect-time (TLS/connection never established) | DNS down | safe — provably nothing sent | `failed`, next tick retries |
| `transport`, post-send (read timeout, dropped mid-response, 5xx) | timeout after request | never automatic — may have posted | `unknown_requires_review` |
| `validation` (incl. empty/oversize text, checked locally first) | 4xx rejection | no (draft problem) | `failed` |
| `permission` / `rate_limit` | scope/429 | no automatic retry | `failed`, recorded |
| `unknown` | unclassified | no | `failed`, recorded |

A 201 with no post id is treated as ambiguity, not success: the store
refuses a `published` row without an id, and the honest record is
`unknown_requires_review`.

## 3. Authentication lifecycle

The credential lives in `Auth_handling/linkedin_tokens.json` (gitignored)
and carries a *duration* (`expires_in`), never an absolute date:

```text
OAuth setup script → token file → every attempt derives expiry →
recorded once in linkedin_credential_expiry with its evidence →
run compares mtime and re-derives on change
```

Expiry derivation: signed `id_token` issuance claim (`id_token_iat`,
authoritative) or file mtime fallback (`file_mtime`); genuinely
underivable expiry is reported unknown, never guessed. Statuses:
`VALID` and `EXPIRING_SOON` publish (`EXPIRING_SOON` ≈ 14 days out,
`LINKEDIN_EXPIRY_WARNING_DAYS`, carries a warning on the successful
result); `MISSING`, `UNREADABLE`, `EXPIRED` refuse before any request as
authentication failures.

What the system deliberately does **not** do: assume programmatic refresh.
The stored credential has no verified refresh path, so expiry is detected,
warned about ahead of time, notified on failure, and fixed by manual
re-authorization (`Auth_handling/linkedin_oauth_setup.py`, verified with
`test_credentials.py`). No automatic refresh is attempted — a rejected or
timed-out refresh would trade a known state for an unverified call.

## 4. Notification behavior

The Step 7 service decides; the Agent never does. Three entry points:

- `notify_run(run_id)` — the workflow wrapper, called once per finished run.
  `DO_NOT_PUBLISH` and unfinished runs are waived (no email, no row, no
  transport touch). Failures and human-intervention outcomes send exactly
  one message composed from the recorded run + failures.
- `notify_failure(failure)` — any recorded phase failure, store optional
  (which is what makes a broken store itself reportable).
- `notify_publication(post)` — a published post, exactly once. A success
  terminates `DO_NOT_PUBLISH` (waived by the failure path), so without this
  call nothing would report what went out under the user's name. No noise
  control applies: a post is an event, not a recurring condition.

One mailbox, one subject (`"Branding Agent"`); the kind (`issue` vs
publication) rides on the message. Repeat suppression: only `sent` rows
count, inside `SMTP_REPEAT_AFTER_HOURS` (default 24h); the first occurrence
always sends; a failed delivery never suppresses anything. Delivery outcome
is a separate `notifications` row — a failed delivery leaves the workflow
failure, its count, and the run outcome untouched (see `recovery.md` §4).

SMTP is entirely environmental (`SMTP_HOST/PORT/SENDER/RECIPIENT/USERNAME/
PASSWORD/TLS/TIMEOUT`, `.env.example` documents them). Unset mail means the
system still runs and records — it just cannot alert, and its delivery rows
say so instead of hiding it. Secrets: `SMTP_PASSWORD` is in the redaction
list; recorded rows carry `host:port tls=mode` only, never credentials or
message bodies.

## 5. Manual path (explicit, never automated)

`Auth_handling/test_post.py`: interactive single-post sender (prints the
text, requires typing `y`), the proven path minus the service layer. Full
procedure: [`../evaluation/manual-linkedin.md`](../evaluation/manual-linkedin.md).
Manual posts bypass intents, duplicate checks, and notifications — do not
reuse post text between manual and autonomous publishing.

## 6. Related

| Document | Role |
|---|---|
| [`../architecture/linkedin-integration.md`](../architecture/linkedin-integration.md) | Integration design |
| [`state-model.md`](state-model.md) | Intent/publication/notification tables |
| [`recovery.md`](recovery.md) | Ambiguity, expiry, delivery-failure procedures |
| [`security.md`](security.md) | Credential and redaction boundary |
