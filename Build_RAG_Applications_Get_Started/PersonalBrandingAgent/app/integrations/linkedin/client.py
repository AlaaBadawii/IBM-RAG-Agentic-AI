"""The low-level LinkedIn API client: URLs, headers, timeouts, payload.

Deliberately thin, and deliberately the only place that knows LinkedIn's
endpoints. It builds and sends requests and hands back whatever came over the
wire; interpreting the answer is :mod:`app.integrations.linkedin.publisher`'s
job, so the classification table has one home.

Two properties are enforced here rather than left to callers:

* **Every request is bounded.** ``timeout`` is always set, from configuration,
  and no code path can omit it. An unattended process that waits on a socket
  forever has not failed — it has stopped, while still holding the run lock.
* **The transport is injectable.** Both HTTP verbs are constructor arguments,
  so tests exercise the real request construction with a fake transport. No
  test in this layer touches the network, and none needs a credential.

The bearer token is passed in as an argument and never stored on the instance,
so a client object is safe to log, reuse, or keep alive across attempts.
"""
from typing import Any, Callable, Mapping

import requests

from app import config

USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"

#: LinkedIn's own requirement for the versioned REST API. Not a secret and not
#: a version: it selects the wire format, which has not changed.
RESTLI_PROTOCOL_VERSION = "2.0.0"


def build_post_payload(author_urn: str, text: str) -> dict[str, Any]:
    """The post body, exactly as the proven manual publish sent it.

    Retained rather than redesigned: this payload is part of what was verified
    against the real API, and Step 5's task is to make the path safe to call
    unattended, not to change what it publishes.
    """
    return {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


class LinkedInClient:
    """Sends LinkedIn requests; returns the responses uninterpreted."""

    def __init__(self, *, api_version: str | None = None,
                 timeout: float | None = None,
                 get: Callable[..., Any] | None = None,
                 post: Callable[..., Any] | None = None) -> None:
        self.api_version = api_version or config.LINKEDIN_API_VERSION
        self.timeout = (timeout if timeout is not None
                        else config.LINKEDIN_TIMEOUT_SECONDS)
        if self.timeout is None or self.timeout <= 0:
            raise ValueError(
                f"LinkedIn requests must be bounded by a positive timeout, "
                f"got {self.timeout!r}"
            )
        # Public so a caller can hand the same transport to the token-refresh
        # path — one injectable seam for one service, rather than two.
        self.get = get or requests.get
        self.post = post or requests.post

    def _headers(self, access_token: str, *,
                 json_body: bool) -> dict[str, str]:
        """Request headers, including the configured API version.

        The version travels in a header LinkedIn retires on a rolling cadence,
        which is why it is configuration: when LinkedIn stops serving it, the
        fix is a value in ``.env``, not an edit here.

        The Authorization header is built here and never logged; callers that
        log headers must not include this one.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": self.api_version,
            "X-Restli-Protocol-Version": RESTLI_PROTOCOL_VERSION,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def fetch_person_urn(self, access_token: str):
        """Ask LinkedIn who this credential belongs to.

        Returns the raw response. The caller turns ``sub`` into an author URN,
        because a malformed identity response is a classification decision and
        classification does not belong here.
        """
        return self.get(
            USERINFO_URL,
            headers=self._headers(access_token, json_body=False),
            timeout=self.timeout,
        )

    def create_post(self, access_token: str, author_urn: str, text: str):
        """Create one post on the credential owner's own profile."""
        return self.post(
            POSTS_URL,
            headers=self._headers(access_token, json_body=True),
            json=build_post_payload(author_urn, text),
            timeout=self.timeout,
        )


def person_urn_from_userinfo(payload: Mapping[str, Any] | None) -> str | None:
    """``urn:li:person:<sub>`` from a userinfo response, or ``None``.

    ``None`` means the response did not identify anyone, which the publisher
    reports rather than guessing an author for.
    """
    if not isinstance(payload, Mapping):
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        return None
    return f"urn:li:person:{subject.strip()}"


def post_id_from_response(response: Any) -> str | None:
    """The created post's id, or ``None`` if LinkedIn did not return one.

    LinkedIn returns it in the ``x-restli-id`` header rather than the body.
    A response without it is *not* treated as a success with a missing id:
    the whole design turns on never claiming a publication that cannot be
    evidenced (``PLAN.md`` §5.1, Step 5).
    """
    headers = getattr(response, "headers", None) or {}
    post_id = headers.get("x-restli-id")
    if isinstance(post_id, str) and post_id.strip():
        return post_id.strip()
    return None
