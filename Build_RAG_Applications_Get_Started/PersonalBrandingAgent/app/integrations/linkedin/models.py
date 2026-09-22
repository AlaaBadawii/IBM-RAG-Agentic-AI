"""Value objects returned by the LinkedIn integration.

Everything here is immutable and carries no behaviour that touches the
network, so a caller can hold a result, compare it, log it, or store it
without triggering anything.

Two rules govern these types:

1. **No secret is ever rendered.** The credential carries the access token
   because it has to, so its ``repr`` is overridden and its secret fields are
   excluded from ``repr`` — a traceback or an f-string must not be able to
   leak a token. Messages and raw response bodies pass through
   :func:`redact` before they are put in a result, for the same reason.
2. **No result claims more than it knows.** A result says a post was
   published only when LinkedIn returned an id for it. Everything else is
   classified, and the ambiguous case says so.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.integrations.linkedin.enums import (
    CredentialStatus,
    LinkedInErrorCategory,
    PublicationOutcome,
)
from app.state.enums import CredentialDerivation

#: How much of an API response body is kept for diagnosis. Long enough for a
#: LinkedIn error message, short enough that a result stays loggable.
MAX_BODY_CHARS = 500


def redact(text: str, *secrets: str | None) -> str:
    """Replace any occurrence of a known secret with ``[REDACTED]``.

    The logging layer already does this for log lines; this is the same
    guarantee applied to values that travel in results rather than through a
    logger, where no filter can reach them.
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def truncate(text: str, limit: int = MAX_BODY_CHARS) -> str:
    """Bound a response body so it can be logged and stored safely."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"…[{len(text) - limit} more chars]"


@dataclass(frozen=True)
class ErrorClassification:
    """What one failure means and what the caller may do about it.

    ``retryable`` is advice about the *failure*, not permission to retry:
    publishing is not idempotent, so whether a retry is safe also depends on
    whether the previous attempt could have reached LinkedIn — which is what
    ``PublicationOutcome`` records. The retry policy itself belongs to Step 6,
    and this layer never retries anything by itself.
    """

    category: LinkedInErrorCategory
    retryable: bool
    requires_human_intervention: bool


@dataclass(frozen=True)
class LinkedInCredential:
    """The credential read from disk, plus what can be derived from it.

    ``expires_at`` is ``None`` only when the stored credential carries neither
    a decodable ``id_token`` nor an ``expires_in`` — in which case the expiry
    is genuinely unknown and is reported as unknown rather than inferred from
    something else (``PLAN.md`` Step 5: never guess).

    ``issuance_evidence`` records which of those two facts the expiry was
    derived from. It is carried on the credential rather than recomputed by
    the caller so that what gets recorded in operational state describes the
    derivation that actually happened.
    """

    source_path: str
    source_mtime: str
    scope: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    expires_in: int | None = None
    issuance_evidence: CredentialDerivation | None = None
    has_refresh_token: bool = False
    access_token: str = field(default="", repr=False)
    refresh_token: str | None = field(default=None, repr=False)

    def secrets(self) -> tuple[str, ...]:
        """Every secret value this credential carries."""
        return tuple(
            value for value in (self.access_token, self.refresh_token) if value
        )

    def redact(self, text: str) -> str:
        """Strip this credential's secrets out of ``text``."""
        return redact(text, *self.secrets())


@dataclass(frozen=True)
class CredentialReport:
    """The credential's lifecycle state, as of one moment.

    This is what an unattended run asks before it does anything: usable or
    not, and if not, why. ``days_remaining`` is ``None`` when the expiry could
    not be derived, which is different from "no days left".
    """

    status: CredentialStatus
    message: str
    expires_at: str | None = None
    days_remaining: float | None = None
    credential: LinkedInCredential | None = None

    @property
    def usable(self) -> bool:
        """True when the credential may be used, including near its expiry."""
        return self.status in (CredentialStatus.VALID,
                               CredentialStatus.EXPIRING_SOON)

    @property
    def expiring_soon(self) -> bool:
        return self.status is CredentialStatus.EXPIRING_SOON

    @property
    def requires_human(self) -> bool:
        """True when nothing but a person re-authorizing can fix this."""
        return self.status in (CredentialStatus.EXPIRED,
                               CredentialStatus.MISSING,
                               CredentialStatus.UNREADABLE)


@dataclass(frozen=True)
class PublicationResult:
    """The outcome of one attempt to publish, and nothing more.

    Every field exists so a caller can decide what to record without parsing
    a message: the outcome, whether a post id came back, the classification,
    what to do about it, and — because a versioned API fails for reasons that
    have nothing to do with the post — the API version the attempt used.
    """

    outcome: PublicationOutcome
    message: str
    api_version: str
    attempted_at: str
    http_status: int | None = None
    post_id: str | None = None
    error_category: LinkedInErrorCategory | None = None
    retryable: bool = False
    requires_human_intervention: bool = False
    credential_status: CredentialStatus | None = None
    expiry_warning: str | None = None
    response_body: str | None = None

    @property
    def published(self) -> bool:
        """True only when LinkedIn returned an id for a post it accepted."""
        return self.outcome is PublicationOutcome.PUBLISHED

    @property
    def ambiguous(self) -> bool:
        """True when it cannot be determined whether a post exists."""
        return self.outcome is PublicationOutcome.UNKNOWN

    @property
    def ok(self) -> bool:
        return self.published


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("refusing to treat a naive datetime as UTC")
    return moment.astimezone(timezone.utc)


def days_until(expires_at: str | None, *, now: datetime) -> float | None:
    """Days from ``now`` until an ISO timestamp, or ``None`` if unknown."""
    if expires_at is None:
        return None
    remaining = datetime.fromisoformat(expires_at) - _utc(now)
    return remaining.total_seconds() / 86400.0
