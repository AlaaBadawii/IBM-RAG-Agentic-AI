"""The classification table: what a response or a broken socket means.

One place decides what every failure category is, so the answer is the same
whether the failure arrived as a status code, a timeout, or a body too large
to send. The categories are ``PLAN.md`` Step 5's, not a new set.

The table is intentionally conservative about one thing above all: whether a
post might exist. Anything that cannot prove the request never left the
machine is ``UNKNOWN``, because a wrong ``FAILED`` would publish a duplicate
on the next run while a wrong ``UNKNOWN`` costs a person five minutes.
"""
import requests

from app.integrations.linkedin.enums import (
    LinkedInErrorCategory,
    PublicationOutcome,
)
from app.integrations.linkedin.models import ErrorClassification

#: For failures that are not LinkedIn's doing and carry no signal: a success
#: response that named no post, an identity response with no member id. There
#: is no error to classify and nothing to branch on, so the honest entry is
#: "unknown, not retryable, no person needed".
UNCLASSIFIED = ErrorClassification(
    category=LinkedInErrorCategory.UNKNOWN,
    retryable=False,
    requires_human_intervention=False,
)


def classify_status(status: int) -> ErrorClassification:
    """Classify a non-success HTTP response from LinkedIn.

    Only called for responses that are not a confirmed publication; the
    caller handles the success path, because success is defined by the
    presence of a post id rather than by a status code.
    """
    if status == 401:
        # The credential is no longer accepted. Nothing about re-sending
        # helps; only re-authorization does.
        return ErrorClassification(
            category=LinkedInErrorCategory.AUTHENTICATION,
            retryable=False,
            requires_human_intervention=True,
        )
    if status == 403:
        # Authenticated but not permitted — the scope is missing, or the
        # application was not granted the capability. Also a person's problem.
        return ErrorClassification(
            category=LinkedInErrorCategory.PERMISSION,
            retryable=False,
            requires_human_intervention=True,
        )
    if status == 429:
        # Explicit backoff signal. Retryable in principle; Step 6 decides
        # whether retrying is safe for the attempt that produced it.
        return ErrorClassification(
            category=LinkedInErrorCategory.RATE_LIMIT,
            retryable=True,
            requires_human_intervention=False,
        )
    if 400 <= status < 500:
        if status == 404:
            # Not a bad post: a missing or retired endpoint. The usual cause
            # is a `LinkedIn-Version` LinkedIn has since stopped serving,
            # which is a configuration change, not a retry.
            return ErrorClassification(
                category=LinkedInErrorCategory.UNKNOWN,
                retryable=False,
                requires_human_intervention=True,
            )
        # The API understood the request and rejected it: too long, malformed
        # field, unsupported combination. The post text is at fault and will
        # fail identically next time.
        return ErrorClassification(
            category=LinkedInErrorCategory.VALIDATION,
            retryable=False,
            requires_human_intervention=False,
        )
    if status >= 500:
        # LinkedIn's own failure, after it received the request. It did not
        # publish, but this is transient and retryable.
        return ErrorClassification(
            category=LinkedInErrorCategory.TRANSPORT,
            retryable=True,
            requires_human_intervention=False,
        )
    # Redirects and unexpected 2xx: no evidence either way.
    return ErrorClassification(
        category=LinkedInErrorCategory.UNKNOWN,
        retryable=False,
        requires_human_intervention=False,
    )


def classify_transport_error(exc: BaseException) -> tuple[ErrorClassification,
                                                          PublicationOutcome]:
    """Classify an exception raised by the HTTP layer.

    Returns both the classification and what is known about the post, because
    for this case the two cannot be decided separately.

    Two outcomes are provable:

    * The TLS handshake failed or the connection was never established — the
      request never reached LinkedIn, so no post exists, and a retry is safe.
    * Anything else — a read timeout, a connection dropped mid-response, a
      protocol error — happened *after* the request was written to a socket
      and may have been processed. Whether a post exists is unknowable from
      here, and it is reported as unknowable.
    """
    if isinstance(exc, (requests.exceptions.ConnectTimeout,
                        requests.exceptions.SSLError)):
        return (
            ErrorClassification(
                category=LinkedInErrorCategory.TRANSPORT,
                retryable=True,
                requires_human_intervention=False,
            ),
            PublicationOutcome.FAILED,
        )
    return (
        ErrorClassification(
            category=LinkedInErrorCategory.TRANSPORT,
            retryable=False,
            requires_human_intervention=False,
        ),
        PublicationOutcome.UNKNOWN,
    )


def validate_commentary(text: str, *, max_chars: int) -> str | None:
    """Check post text before spending a request on it.

    Returns the reason the text is unusable, or ``None`` if it is fine. This
    is the same judgement the API would make, made locally so an obvious
    mistake is classified immediately and without a round trip.
    """
    stripped = text.strip()
    if not stripped:
        return "post text is empty"
    if len(text) > max_chars:
        return (f"post text is {len(text)} characters; LinkedIn accepts at "
                f"most {max_chars}")
    return None
