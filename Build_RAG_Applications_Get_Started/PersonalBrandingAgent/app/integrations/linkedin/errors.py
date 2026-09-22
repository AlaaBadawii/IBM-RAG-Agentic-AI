"""Errors raised *inside* the LinkedIn integration, and never outside it.

The integration's contract with its callers is a structured result, not an
exception: a caller that can receive a ``PublicationResult`` can always tell
whether a post exists, which is the property ``PLAN.md`` Step 5 insists on.
Raising would move that judgement to whoever remembered to catch.

So this module's exception exists for the short distance between "the
credential file could not be read" and "the report that says so". It is
translated into a result before it can escape the package.
"""
from app.errors import AppError


class LinkedInIntegrationError(AppError):
    """Base class for failures raised inside the LinkedIn integration."""


class CredentialError(LinkedInIntegrationError):
    """The stored credential is missing, unreadable, or structurally wrong.

    A local, deterministic condition — no request was attempted, and nothing
    about it is transient.
    """


class CredentialMissingError(CredentialError):
    """There is no credential file at all.

    Separate from the other credential failures because the remedy is
    different in kind: nothing is broken, the user simply has never
    authorized, or the file was removed. The reported status distinguishes
    them for the same reason.
    """
