"""``publish_to_linkedin`` — the one function the rest of the system calls.

    publish_to_linkedin(post_text) -> PublicationResult

Nothing above this module knows about endpoints, headers, tokens, or HTTP.
Nothing here knows what the text says, where it came from, or whether it
should have been published: those are the caller's decisions, and the
integration is not entitled to a view on them.

What this module guarantees, in the order it checks them:

1. **The text is publishable.** Empty and oversized drafts are rejected
   locally, as validation failures, before a request is spent on them.
2. **The credential is usable.** Missing, unreadable, and expired credentials
   are authentication failures that require a person — never retried, because
   nothing about them improves by trying again.
3. **Every request is bounded** (see :mod:`~app.integrations.linkedin.client`).
4. **Every failure is classified and returned**, never raised and never
   printed. The caller always learns what happened and whether a post might
   exist; only a state-store failure escapes, and that happens before any
   request is sent.
5. **A publication is claimed only on evidence** — a success status *and* a
   post id. Anything else is ``FAILED`` or, when the request may have been
   received, ``UNKNOWN``.

This module records nothing about publishing. The result is the whole output:
persisting the intent, the attempt, and the outcome belongs to Step 6, which
is the only layer allowed to decide that a post was published.
"""
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from app import config
from app.integrations.linkedin import client as client_module
from app.integrations.linkedin.classification import (
    UNCLASSIFIED,
    classify_status,
    classify_transport_error,
    validate_commentary,
)
from app.integrations.linkedin.credentials import check_credential
from app.integrations.linkedin.enums import (
    CredentialStatus,
    LinkedInErrorCategory,
    PublicationOutcome,
)
from app.integrations.linkedin.models import (
    PublicationResult,
    truncate,
)
from app.logging_config import get_logger
from app.state import StateStore
from app.state.models import to_iso

logger = get_logger(__name__)


def _now(moment: datetime | None) -> datetime:
    return moment or datetime.now(timezone.utc)


def _response_body(response: Any, credential_secrets: tuple[str, ...]) -> str:
    """The response body, bounded and stripped of any credential value."""
    text = getattr(response, "text", "")
    if not isinstance(text, str):
        text = str(text)
    for secret in credential_secrets:
        text = text.replace(secret, "[REDACTED]")
    return truncate(text)


def _failure(*, api_version: str, attempted_at: str, message: str,
             credential=None, credential_status: CredentialStatus | None = None,
             expiry_warning: str | None = None,
             http_status: int | None = None,
             classification=None, outcome: PublicationOutcome,
             response_body: str | None = None) -> PublicationResult:
    """Build a failure result with its message scrubbed of any secret."""
    if credential is not None:
        message = credential.redact(message)
    return PublicationResult(
        outcome=outcome,
        message=message,
        api_version=api_version,
        attempted_at=attempted_at,
        http_status=http_status,
        error_category=(classification.category if classification else
                        LinkedInErrorCategory.UNKNOWN),
        retryable=bool(classification and classification.retryable),
        requires_human_intervention=bool(
            classification and classification.requires_human_intervention
        ),
        credential_status=credential_status,
        expiry_warning=expiry_warning,
        response_body=response_body,
    )


def _credential_expiry_warning(report) -> str | None:
    """The warning a successful publish must carry forward, if any.

    A publish can succeed and still leave the system days away from failing
    every run; the caller needs both facts from one call, or the warning is
    only ever delivered by the run that no longer works.
    """
    return report.message if report is not None and report.expiring_soon else None


def publish_to_linkedin(post_text: str, *,
                        store: StateStore | None = None,
                        client: client_module.LinkedInClient | None = None,
                        token_path: Any | None = None,
                        now: datetime | None = None) -> PublicationResult:
    """Publish one post to the credential owner's own LinkedIn profile.

    ``store`` is optional and used only to record when the credential expires
    — the lifecycle fact a later run needs in order to warn before it fails.
    Nothing about the publication itself is written anywhere by this function.

    Raises :class:`~app.errors.StateStoreError` when a store was supplied and
    could not be written. That happens before any request is sent, and it is
    deliberate: the store is the system's durable memory, and a run that
    cannot record what it observed must not go on to publish (``PLAN.md`` §11).
    """
    active = client or client_module.LinkedInClient()
    attempted_at = to_iso(_now(now))
    api_version = active.api_version

    reason = validate_commentary(
        post_text if isinstance(post_text, str) else "",
        max_chars=config.LINKEDIN_MAX_COMMENTARY_CHARS,
    )
    if reason is not None:
        return _failure(
            api_version=api_version, attempted_at=attempted_at,
            message=reason,
            classification=classify_status(422),
            outcome=PublicationOutcome.FAILED,
        )

    report = check_credential(path=token_path, store=store, now=now,
                              post=active.post,
                              timeout=active.timeout)
    warning = _credential_expiry_warning(report)

    if not report.usable or report.credential is None:
        # A credential problem is never transient, so there is nothing to
        # retry and nothing to send. The run stops and asks for a person.
        logger.warning("LinkedIn publish refused: %s", report.message)
        return _failure(
            api_version=api_version, attempted_at=attempted_at,
            message=report.message,
            credential_status=report.status,
            classification=classify_status(401),
            outcome=PublicationOutcome.FAILED,
        )

    credential = report.credential
    secrets = credential.secrets()

    urn_response, failure = _send(active.fetch_person_urn,
                                  credential.access_token,
                                  api_version=api_version,
                                  attempted_at=attempted_at,
                                  credential=credential,
                                  credential_status=report.status,
                                  expiry_warning=warning,
                                  step="resolving the LinkedIn member id")
    if failure is not None:
        return failure

    if urn_response.status_code != 200:
        return _http_failure(
            urn_response, api_version=api_version, attempted_at=attempted_at,
            credential=credential, credential_status=report.status,
            expiry_warning=warning,
            message=(f"LinkedIn refused to identify the credential owner "
                     f"(HTTP {urn_response.status_code}); the credential may "
                     f"lack the openid/profile scope"),
        )

    try:
        author_urn = client_module.person_urn_from_userinfo(urn_response.json())
    except ValueError:
        author_urn = None
    if author_urn is None:
        return _failure(
            api_version=api_version, attempted_at=attempted_at,
            message=("LinkedIn's identity response contained no member id, so "
                     "the post has no author and was not attempted"),
            credential=credential, credential_status=report.status,
            expiry_warning=warning,
            classification=UNCLASSIFIED,
            outcome=PublicationOutcome.FAILED,
            response_body=_response_body(urn_response, secrets),
        )

    post_response, failure = _send(
        lambda token: active.create_post(token, author_urn, post_text),
        credential.access_token,
        api_version=api_version, attempted_at=attempted_at,
        credential=credential, credential_status=report.status,
        expiry_warning=warning,
        step="creating the post",
    )
    if failure is not None:
        return failure

    body = _response_body(post_response, secrets)
    if post_response.status_code in (200, 201):
        post_id = client_module.post_id_from_response(post_response)
        if post_id is None:
            # Accepted, but with nothing to point at. LinkedIn does not offer
            # read-back, so this cannot be resolved by asking — it is exactly
            # the ambiguous outcome the design must be able to express.
            return _failure(
                api_version=api_version, attempted_at=attempted_at,
                message=("LinkedIn accepted the request but returned no post "
                         "id, so it cannot be confirmed that a post exists"),
                credential=credential, credential_status=report.status,
                expiry_warning=warning,
                http_status=post_response.status_code,
                classification=UNCLASSIFIED,
                outcome=PublicationOutcome.UNKNOWN,
                response_body=body,
            )
        logger.info("Published to LinkedIn: %s (API version %s)",
                    post_id, api_version)
        return PublicationResult(
            outcome=PublicationOutcome.PUBLISHED,
            message=f"published to LinkedIn as {post_id}",
            api_version=api_version,
            attempted_at=attempted_at,
            http_status=post_response.status_code,
            post_id=post_id,
            credential_status=report.status,
            expiry_warning=warning,
            response_body=body,
        )

    return _http_failure(
        post_response, api_version=api_version, attempted_at=attempted_at,
        credential=credential, credential_status=report.status,
        expiry_warning=warning,
        message=(f"LinkedIn rejected the post with HTTP "
                 f"{post_response.status_code}"),
    )


def _send(call: Callable[[str], Any], access_token: str, *,
          api_version: str, attempted_at: str, credential,
          credential_status: CredentialStatus,
          expiry_warning: str | None,
          step: str) -> tuple[Any | None, PublicationResult | None]:
    """Perform one request, converting a transport failure into a result.

    Transport failures are the only case where the request may have reached
    LinkedIn and the answer was never heard; that is why the outcome here is
    decided by the classification rather than by the caller.
    """
    try:
        return call(access_token), None
    except requests.RequestException as exc:
        classification, outcome = classify_transport_error(exc)
        logger.warning("LinkedIn request failed while %s: %s", step, exc)
        return None, _failure(
            api_version=api_version, attempted_at=attempted_at,
            message=(f"LinkedIn request failed while {step}: "
                     f"{type(exc).__name__}"),
            credential=credential, credential_status=credential_status,
            expiry_warning=expiry_warning,
            classification=classification, outcome=outcome,
        )


def _http_failure(response: Any, *, api_version: str, attempted_at: str,
                  credential, credential_status: CredentialStatus,
                  expiry_warning: str | None, message: str
                  ) -> PublicationResult:
    """Classify a response that was received and is not a publication."""
    status = response.status_code
    classification = classify_status(status)
    if classification.requires_human_intervention:
        logger.warning("LinkedIn publish requires human intervention: %s "
                       "(HTTP %s)", message, status)
    else:
        logger.warning("LinkedIn publish failed: %s (HTTP %s)", message, status)
    return _failure(
        api_version=api_version, attempted_at=attempted_at,
        message=message, credential=credential,
        credential_status=credential_status, expiry_warning=expiry_warning,
        http_status=status, classification=classification,
        outcome=PublicationOutcome.FAILED,
        response_body=_response_body(response, credential.secrets()),
    )


__all__ = ["publish_to_linkedin"]
