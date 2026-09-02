# LinkedIn Integration

## Existing assets

The repository already contains a working LinkedIn OAuth implementation under
`Auth_handling/`:

| File | Purpose |
|---|---|
| `linkedin_oauth_setup.py` | One-time OAuth: browser consent, callback on `localhost:8000`, code exchange, tokens saved to `linkedin_tokens.json` |
| `test_credentials.py` | Validates saved access token, refreshes when expired, checks `userinfo` endpoint |
| `test_post.py` | Loads token, resolves the person URN, posts a test post to `/rest/posts` |

These scripts work and are **not rewritten unnecessarily**. The integration
phase (Phase 8) builds a clean, reusable layer around them.

## Integration layer

The Agent should never touch OAuth internals. It interacts with a defined tool
interface:

```python
publish_to_linkedin(post_text) -> PublicationResult
```

Target module layout:

```text
app/integrations/linkedin/
    client.py     # low-level LinkedIn API client (requests)
    auth.py       # token loading + refresh (wraps Auth_handling logic)
    publisher.py  # high-level publish_to_linkedin() used by the Agent
```

The integration layer is responsible for:

- token loading and refresh (reuse the refresh logic proven in
  `test_credentials.py`)
- API request construction
- LinkedIn API version header (the client pins `LinkedIn-Version`; current
  value in `test_post.py` is `202607`)
- request validation (e.g., empty/oversized text, reserved characters)
- API error handling and classification
- response parsing and extracting the publication id
- logging (without logging tokens or secrets)

## Publishing flow

```text
Agent ──► publisher.publish_to_linkedin(text)
              │
              ├─ auth.get_valid_access_token()   (refresh if 401/expired)
              ├─ client.create_post(text)        → LinkedIn API
              ├─ parse response
              └─ return PublicationResult(post_id, raw_response, ok)
```

The publisher returns a structured `PublicationResult` so the Agent can record
it accurately and never claim a false publish.

## Credentials and scopes

- Credentials live in the environment (`.env`): `LINKEDIN_CLIENT_ID`,
  `LINKEDIN_CLIENT_SECRET`. Tokens live in `Auth_handling/linkedin_tokens.json`.
- Both are excluded from source control (see `../operations/security.md`).
- OAuth scope used: `openid profile w_member_social email`
  (`w_member_social` grants post-to-profile permission).
- The app posts to the user's own profile only.

## Error handling and failure policy

| Situation | Behavior |
|---|---|
| Access token expired | Refresh via `refresh_token`; if refresh fails, fail with `auth_failed` |
| HTTP 401/403 | Do not retry blindly; surface the error and status |
| API 4xx | Classify (validation vs auth vs permission); surface to caller |
| API 5xx / network | Safe retry with backoff, bounded retries; do not report published |
| Timeout | Fail safely; never mark as published |
| Response without post id | Treat as failed/ambiguous; do not record as published |
| Possible duplicate (network retry) | Detect via recorded history; do not retry blindly |

The Agent must **never** mark a post as published unless LinkedIn returned a
success response containing a post id.

## Preventing duplicate posts

- Every successful publish returns a LinkedIn post id.
- `record_publication()` stores that id in operational memory.
- Before publishing, the Agent can check history for recent/identical posts
  (see `../evaluation/quality-gates.md` duplication check).

## Security notes

- Never log access tokens, refresh tokens, client secrets, or full
  authorization headers.
- Keep tokens out of git (already enforced by `.gitignore`).
- If a token is exposed (committed, leaked in logs), rotate it via LinkedIn
  developer console and re-run `linkedin_oauth_setup.py`.
- The tool authorizes publishing to the user's own profile only; it does not
  manage pages or other members' accounts.
- Rate limits: respect LinkedIn API rate limits; use bounded retries with
  backoff; treat `429` as a backoff signal.

## Related documents

- Operations/security: `../operations/security.md`
- Tool phase: `../phases/phase-08-linkedin-tools.md`
- Data flow: `data-flow.md`