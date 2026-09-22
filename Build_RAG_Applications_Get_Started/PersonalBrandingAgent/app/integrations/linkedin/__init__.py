"""LinkedIn integration boundary.

One function publishes; everything else is there so the caller can find out
whether it is safe to call it.

    from app.integrations.linkedin import check_credential, publish_to_linkedin

    report = check_credential(store=store)      # warn before the failure
    result = publish_to_linkedin(text, store=store)
    if result.published:
        ...                                     # Step 6 records the intent
    elif result.ambiguous:
        ...                                     # a person has to look

The layering is the point (``PLAN.md`` Step 5, architectural placement):

    LinkedIn API  →  this package  →  the publishing/state layers

Nothing above this package speaks HTTP, and this package knows nothing about
generation, retrieval, or what a workflow run is. It returns structured
results and stores exactly one fact — when the credential expires — because
the caller owns every decision about publishing.

Rewrite status: the OAuth flow, the endpoint, the payload, and the person-URN
resolution are the proven ones, retained. What is new is that they are
reachable without a person at the keyboard.
"""
from app.integrations.linkedin.credentials import (
    CREDENTIAL_NAME,
    check_credential,
    evaluate_credential,
    load_credential,
    record_expiry,
)
from app.integrations.linkedin.client import LinkedInClient
from app.integrations.linkedin.enums import (
    CredentialStatus,
    LinkedInErrorCategory,
    PublicationOutcome,
)
from app.integrations.linkedin.errors import CredentialError
from app.integrations.linkedin.models import (
    CredentialReport,
    LinkedInCredential,
    PublicationResult,
)
from app.integrations.linkedin.publisher import publish_to_linkedin

__all__ = [
    "CREDENTIAL_NAME",
    "CredentialError",
    "CredentialReport",
    "CredentialStatus",
    "LinkedInClient",
    "LinkedInCredential",
    "LinkedInErrorCategory",
    "PublicationOutcome",
    "PublicationResult",
    "check_credential",
    "evaluate_credential",
    "load_credential",
    "publish_to_linkedin",
    "record_expiry",
]
