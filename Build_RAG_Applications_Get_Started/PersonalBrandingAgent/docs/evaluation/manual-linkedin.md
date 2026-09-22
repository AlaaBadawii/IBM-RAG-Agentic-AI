# Manual Real-LinkedIn Path

The one deliberate way to publish a real post (`PLAN.md` Step 13: the real
LinkedIn path stays manual and explicitly invoked). The evaluation suite
never touches it — every scenario uses fakes — and nothing automated may
call it.

---

## 1. Prerequisites

1. A LinkedIn application with the `w_member_social`, `openid`, `profile`,
   and `email` scopes (see `docs/architecture/linkedin-integration.md`).
2. Project secrets in the repository-root `.env` (gitignored, never
   committed — see `docs/operations/security.md`).
3. The project-local environment (`.venv`).

## 2. Authorize once

```bash
cd Auth_handling
../.venv/bin/python linkedin_oauth_setup.py
```

This performs the OAuth exchange in the browser and writes
`Auth_handling/linkedin_tokens.json` (gitignored). Re-authorize when the
token expires — the unattended system cannot renew it itself and reports
`REQUIRES_HUMAN_INTERVENTION` instead (evaluation scenario 13 proves the
workflow side of that contract).

## 3. Send one explicit test post

```bash
cd Auth_handling
../.venv/bin/python test_post.py
```

What this does, step by step:

1. Loads the access token from `linkedin_tokens.json` (resolved relative to
   the script file, never to the working directory).
2. Resolves the member id via `GET /v2/userinfo`.
3. Prints the exact post text and asks for interactive confirmation —
   **nothing publishes without typing `y`**.
4. On confirmation, sends one `POST /rest/posts` and prints the LinkedIn
   post id from the `x-restli-id` response header.

`Auth_handling/test_credentials.py` verifies the credential without posting
and is the safe first check after authorizing.

## 4. Boundaries

- This path is **outside** the autonomous workflows: no run record, no
  write-ahead intent, no duplicate check, no notification. A manually posted
  text is unknown to the Step 6 duplicate policy — do not reuse post text
  between manual and autonomous publishing.
- The unattended equivalent of this request is
  `app/integrations/linkedin/publish_to_linkedin`, wrapped by the Step 6
  publishing service. Same endpoint and payload; the service adds the intent,
  the outcome record, the duplicate checks, and the error classification this
  script does not have.
- Never commit `linkedin_tokens.json`, never paste a token into a document
  or a log, and never run this script from automation.
