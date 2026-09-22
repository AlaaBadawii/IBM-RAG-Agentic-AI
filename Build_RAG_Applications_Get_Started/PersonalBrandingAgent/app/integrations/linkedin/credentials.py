"""The credential's lifecycle: where it is, when it dies, what to do about it.

The integration was proven interactively, by a person who could see the
failure on screen. An unattended run cannot: it has to ask these questions
*before* it needs the answer, because the failure being avoided only shows up
as a 401 in the middle of a publish.

Three commitments shape this module.

**Expiry is read, never guessed.** The stored credential holds a duration
(``expires_in``) and, in the ``id_token`` LinkedIn signed, the moment it was
issued. Expiry is issuance plus duration; when the issuance claim is missing,
the moment the file was written is the fallback. If neither exists, the
expiry is reported as unknown — an unknown expiry is not an invitation to
assume the token is fine.

**Refresh is attempted, never assumed.** If the credential carries no refresh
token, no refresh is attempted and the failure stays a credential failure.
That is the real state of the stored credential today (``PLAN.md`` §5.2): the
flow below is correct without refresh, and would become *more* useful, not
different in kind, if refresh were ever verified to work.

**No secret leaves this module.** The credential redacts its own ``repr``;
messages here name the file and the condition, never the value.
"""
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import requests

from app import config, paths
from app.integrations.linkedin.enums import CredentialStatus
from app.integrations.linkedin.errors import (
    CredentialError,
    CredentialMissingError,
)
from app.integrations.linkedin.models import (
    CredentialReport,
    LinkedInCredential,
    days_until,
)
from app.logging_config import get_logger
from app.state.enums import CredentialDerivation
from app.state.models import to_iso

logger = get_logger(__name__)

#: The name this credential is recorded under in operational state. One row,
#: because there is one LinkedIn account and the system posts to it.
CREDENTIAL_NAME = "linkedin_access_token"

REFRESH_URL = "https://www.linkedin.com/oauth/v2/accessToken"

#: The credential holds a bearer token for a real account; nothing else on
#: the machine needs to read it.
_TOKEN_FILE_MODE = 0o600


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise CredentialMissingError(
            f"no LinkedIn credential at {path}: run "
            f"Auth_handling/linkedin_oauth_setup.py to authorize"
        )
    try:
        with open(path, encoding="utf-8") as handle:
            tokens = json.load(handle)
    except ValueError as exc:
        raise CredentialError(
            f"the LinkedIn credential at {path} is not valid JSON; re-run "
            f"Auth_handling/linkedin_oauth_setup.py"
        ) from exc
    except OSError as exc:
        raise CredentialError(
            f"the LinkedIn credential at {path} could not be read: {exc}"
        ) from exc
    if not isinstance(tokens, dict):
        raise CredentialError(f"the LinkedIn credential at {path} is not a "
                              f"JSON object")
    return tokens


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):  # bool is an int in Python; never a duration
        return None
    return value if isinstance(value, int) else None


def issued_at_from_id_token(id_token: object) -> datetime | None:
    """The ``iat`` claim of the credential's id token, if it has one.

    The signature is deliberately not verified: this is our own credential,
    read from our own disk, and the claim dates a file rather than authorizing
    anything. Verifying it would mean fetching and caching LinkedIn's signing
    keys to learn something already known — the file was written when the
    token was issued.
    """
    if not isinstance(id_token, str) or id_token.count(".") < 2:
        return None
    payload = id_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)  # restore stripped base64 padding
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    issued = _int_or_none(claims.get("iat"))
    if issued is None:
        return None
    try:
        return datetime.fromtimestamp(issued, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def load_credential(path: Path | str | None = None) -> LinkedInCredential:
    """Read the stored credential and everything derivable from it.

    Raises :class:`CredentialError` — and only that — for every way the file
    can be wrong, so a caller has exactly one thing to translate into a
    result.
    """
    token_path = Path(path) if path is not None else paths.LINKEDIN_TOKEN_FILE
    tokens = _load_json(token_path)

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise CredentialError(
            f"the LinkedIn credential at {token_path} has no access_token; "
            f"re-run Auth_handling/linkedin_oauth_setup.py"
        )

    mtime = datetime.fromtimestamp(token_path.stat().st_mtime, tz=timezone.utc)
    expires_in = _int_or_none(tokens.get("expires_in"))
    refresh_token = tokens.get("refresh_token")

    issued_at = issued_at_from_id_token(tokens.get("id_token"))
    evidence = CredentialDerivation.ID_TOKEN_IAT if issued_at is not None else None
    if issued_at is None and expires_in is not None:
        # No signed issuance claim. The moment the file was written is the
        # best evidence available, and it is evidence rather than a guess
        # because the exchange that issues the token is what writes the file.
        issued_at, evidence = mtime, CredentialDerivation.FILE_MTIME

    expires_at = (
        issued_at + timedelta(seconds=expires_in)
        if issued_at is not None and expires_in is not None
        else None
    )

    return LinkedInCredential(
        source_path=str(token_path),
        source_mtime=to_iso(mtime),
        scope=tokens.get("scope") if isinstance(tokens.get("scope"), str) else None,
        issued_at=to_iso(issued_at) if issued_at is not None else None,
        expires_at=to_iso(expires_at) if expires_at is not None else None,
        expires_in=expires_in,
        issuance_evidence=evidence,
        has_refresh_token=isinstance(refresh_token, str) and bool(refresh_token),
        access_token=access_token,
        refresh_token=refresh_token if isinstance(refresh_token, str) else None,
    )


def evaluate_credential(credential: LinkedInCredential, *,
                        now: datetime | None = None,
                        warning_days: int | None = None) -> CredentialReport:
    """Decide whether the credential is usable, without touching the network."""
    moment = now or datetime.now(timezone.utc)
    window = (config.LINKEDIN_EXPIRY_WARNING_DAYS if warning_days is None
              else warning_days)
    remaining = days_until(credential.expires_at, now=moment)

    if remaining is None:
        return CredentialReport(
            status=CredentialStatus.VALID,
            message=(
                "credential expiry is unknown: the stored credential carries "
                "no decodable id_token and no expires_in, so no expiry warning "
                "can be given. If publishing starts failing with 401, "
                "re-authorize with Auth_handling/linkedin_oauth_setup.py"
            ),
            credential=credential,
        )
    if remaining <= 0:
        return CredentialReport(
            status=CredentialStatus.EXPIRED,
            message=(
                f"the LinkedIn credential expired on {credential.expires_at} "
                f"({abs(remaining):.1f} days ago) and cannot be renewed "
                f"automatically; re-authorize by running "
                f"Auth_handling/linkedin_oauth_setup.py"
            ),
            expires_at=credential.expires_at,
            days_remaining=remaining,
            credential=credential,
        )
    if remaining <= window:
        return CredentialReport(
            status=CredentialStatus.EXPIRING_SOON,
            message=(
                f"the LinkedIn credential expires on {credential.expires_at} "
                f"({remaining:.1f} days from now); re-authorize by running "
                f"Auth_handling/linkedin_oauth_setup.py before then"
            ),
            expires_at=credential.expires_at,
            days_remaining=remaining,
            credential=credential,
        )
    return CredentialReport(
        status=CredentialStatus.VALID,
        message=(
            f"the LinkedIn credential is valid until {credential.expires_at} "
            f"({remaining:.1f} days)"
        ),
        expires_at=credential.expires_at,
        days_remaining=remaining,
        credential=credential,
    )


def record_expiry(store, report: CredentialReport) -> None:
    """Record a derived expiry in operational state.

    Skipped when the expiry is unknown: there is no row that would be true,
    and a placeholder would be read back later as if it were. A store failure
    is deliberately **not** caught — the store is the system's durable memory,
    and a run that cannot record what it observed must not go on to publish
    (``PLAN.md`` §11, note on store failure).
    """
    credential = report.credential
    if store is None or report.expires_at is None or credential is None:
        return
    if credential.issuance_evidence is None:
        return
    store.record_credential_expiry(
        credential=CREDENTIAL_NAME,
        expires_at=report.expires_at,
        issued_at=credential.issued_at,
        derived_from=credential.issuance_evidence,
        source_mtime=credential.source_mtime,
    )


def check_credential(*, path: Path | str | None = None, store=None,
                     now: datetime | None = None, refresh: bool = True,
                     post: Callable | None = None,
                     timeout: float | None = None) -> CredentialReport:
    """The full lifecycle check: read, evaluate, refresh if needed, record.

    Answers with a report for every state the credential can be in —
    including "missing", which is a report rather than an exception, because
    an unattended run has to record and notify rather than crash.

    A refresh is attempted only when the credential is **already expired** and
    carries a refresh token. Refreshing ahead of expiry would trade a certain,
    warnable failure for an unverified code path (``PLAN.md`` §5.2).
    """
    try:
        credential = load_credential(path)
    except CredentialMissingError as exc:
        return CredentialReport(status=CredentialStatus.MISSING,
                                message=str(exc))
    except CredentialError as exc:
        return CredentialReport(status=CredentialStatus.UNREADABLE,
                                message=str(exc))

    report = evaluate_credential(credential, now=now)
    record_expiry(store, report)

    if report.status is CredentialStatus.EXPIRED and refresh:
        refreshed = _refresh_if_possible(credential, path=path, post=post,
                                         timeout=timeout)
        if refreshed is not None:
            report = evaluate_credential(refreshed, now=now)
            record_expiry(store, report)

    if report.expiring_soon:
        logger.warning("LinkedIn credential expiring soon: %s", report.message)
    return report


def _refresh_if_possible(credential: LinkedInCredential, *,
                         path: Path | str | None = None,
                         post: Callable | None = None,
                         timeout: float | None = None
                         ) -> LinkedInCredential | None:
    """Exchange the refresh token for a new access token, or return ``None``.

    ``None`` means no refresh was performed — there is no refresh token, or
    the OAuth application credentials are not configured, or the exchange did
    not succeed. None of those is a surprise: the caller already holds a
    report saying the credential is expired, and the remedy is the same in
    every case.
    """
    if not credential.has_refresh_token:
        return None
    client_id = config.LINKEDIN_CLIENT_ID
    client_secret = config.LINKEDIN_CLIENT_SECRET
    if not client_id or not client_secret:
        logger.warning(
            "the LinkedIn credential is expired and cannot be refreshed: "
            "LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET are not set"
        )
        return None

    send = post or requests.post
    try:
        response = send(
            REFRESH_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": credential.refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=(timeout if timeout is not None
                     else config.LINKEDIN_TIMEOUT_SECONDS),
        )
    except requests.RequestException as exc:
        logger.warning("LinkedIn token refresh failed: %s", exc)
        return None

    if getattr(response, "status_code", None) != 200:
        logger.warning("LinkedIn token refresh was rejected with status %s",
                       getattr(response, "status_code", "unknown"))
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning("LinkedIn token refresh returned a non-JSON body")
        return None
    if not isinstance(payload, dict) or not payload.get("access_token"):
        logger.warning("LinkedIn token refresh returned no access token")
        return None

    return _persist_refreshed(credential, payload, path=path)


def _persist_refreshed(credential: LinkedInCredential, payload: dict, *,
                       path: Path | str | None = None) -> LinkedInCredential:
    """Write refreshed tokens back to the credential file, then re-read it.

    Written to a temporary file in the same directory and moved into place, so
    an interrupted write cannot leave a truncated credential behind: losing
    the only copy of the token would mean re-authorizing by hand, which is the
    cost this path exists to avoid.
    """
    token_path = Path(path) if path is not None else paths.LINKEDIN_TOKEN_FILE
    updated = dict(_load_json(token_path))
    updated.update(payload)

    temporary = token_path.with_suffix(token_path.suffix + ".tmp")
    descriptor = os.open(temporary,
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         _TOKEN_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), _TOKEN_FILE_MODE)
        json.dump(updated, handle, indent=2)
    os.replace(temporary, token_path)

    logger.info("LinkedIn access token refreshed and saved to %s", token_path)
    return load_credential(token_path)
