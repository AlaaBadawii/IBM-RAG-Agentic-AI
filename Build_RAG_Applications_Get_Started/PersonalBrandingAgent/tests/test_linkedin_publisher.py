"""Step 5: ``publish_to_linkedin`` — the boundary the workflow calls.

No test here touches the network, needs a real credential, or publishes
anything. The transport is a fake; the token file is written fresh under
``tmp_path``.

What these tests are really checking is the sentence ``PLAN.md`` Step 5 ends
its failure section with: *the integration never raises into a state where the
caller cannot tell whether a post exists*. Every failure path below asserts
that a caller can still decide.
"""
import json
import os
from datetime import datetime, timezone

import pytest
import requests

from app import config, paths
from app.errors import StateStoreError
from app.integrations.linkedin import publish_to_linkedin
from app.integrations.linkedin.client import (
    POSTS_URL,
    USERINFO_URL,
    LinkedInClient,
)
from app.integrations.linkedin.credentials import CREDENTIAL_NAME
from app.integrations.linkedin.enums import (
    CredentialStatus,
    LinkedInErrorCategory,
    PublicationOutcome,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
TOKEN = "fake-access-token-value"
POST_ID = "urn:li:share:7123456789"
TEXT = "A post about a thing I built."


class Call:
    def __init__(self, method, url, kwargs):
        self.method, self.url, self.kwargs = method, url, kwargs

    @property
    def headers(self):
        return self.kwargs["headers"]

    @property
    def timeout(self):
        return self.kwargs.get("timeout")


class FakeTransport:
    """Answers the two LinkedIn endpoints, and records what it was asked."""

    def __init__(self, *, userinfo=None, post=None):
        self.userinfo = userinfo
        self.post_response = post
        self.calls: list[Call] = []

    def _record(self, method, url, kwargs, answer):
        self.calls.append(Call(method, url, kwargs))
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get(self, url, **kwargs):
        return self._record("GET", url, kwargs, self.userinfo)

    def post(self, url, **kwargs):
        return self._record("POST", url, kwargs, self.post_response)


def response(status, *, body="", headers=None):
    built = requests.Response()
    built.status_code = status
    built._content = body.encode()
    built.headers.update(headers or {})
    return built


def identity(sub="abc123"):
    return response(200, body=json.dumps({"sub": sub}),
                    headers={"Content-Type": "application/json"})


def published(post_id=POST_ID):
    return response(201, headers={"x-restli-id": post_id})


def credentialed(tmp_path, *, expires_in=5183999, id_token_issued=None,
                 refresh_token=None, access_token=TOKEN):
    """Write a credential file good for ``expires_in`` seconds from NOW."""
    issued = id_token_issued if id_token_issued is not None else NOW
    payload = {
        "access_token": access_token,
        "expires_in": expires_in,
        "scope": "email,openid,profile,w_member_social",
        "id_token": _unsigned_id_token(issued),
    }
    if refresh_token is not None:
        payload["refresh_token"] = refresh_token
    path = tmp_path / "linkedin_tokens.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (NOW.timestamp(), NOW.timestamp()))
    return path


def _unsigned_id_token(issued_at):
    import base64

    claims = json.dumps({"iat": int(issued_at.timestamp())}).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def publish(transport, token_path, **kwargs):
    return publish_to_linkedin(
        kwargs.pop("text", TEXT),
        client=LinkedInClient(get=transport.get, post=transport.post,
                              api_version="202607"),
        token_path=token_path,
        now=NOW,
        **kwargs,
    )


# --- success -----------------------------------------------------------------

def test_a_successful_publish_returns_the_linkedin_post_id(tmp_path):
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish(transport, credentialed(tmp_path))

    assert result.published is True
    assert result.ok is True
    assert result.ambiguous is False
    assert result.post_id == POST_ID
    assert result.http_status == 201
    assert result.error_category is None
    assert result.retryable is False
    assert result.requires_human_intervention is False
    assert POST_ID in result.message


def test_the_publish_sends_the_proven_request(tmp_path):
    transport = FakeTransport(userinfo=identity(), post=published())
    publish(transport, credentialed(tmp_path))

    userinfo, posts = transport.calls
    assert (userinfo.method, userinfo.url) == ("GET", USERINFO_URL)
    assert (posts.method, posts.url) == ("POST", POSTS_URL)
    assert posts.kwargs["json"]["author"] == "urn:li:person:abc123"
    assert posts.kwargs["json"]["commentary"] == TEXT


def test_every_request_made_during_a_publish_is_bounded(tmp_path):
    transport = FakeTransport(userinfo=identity(), post=published())
    publish(transport, credentialed(tmp_path))

    assert [call.timeout for call in transport.calls] == [
        config.LINKEDIN_TIMEOUT_SECONDS, config.LINKEDIN_TIMEOUT_SECONDS
    ]


def test_the_api_version_used_is_recorded_with_the_attempt(tmp_path):
    """A versioned API fails for reasons unrelated to the post."""
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish(transport, credentialed(tmp_path))

    assert result.api_version == "202607"
    assert transport.calls[1].headers["LinkedIn-Version"] == "202607"


def test_a_successful_publish_still_carries_the_expiry_warning(tmp_path):
    """The warning must not wait for the run that no longer works."""
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish(transport,
                     credentialed(tmp_path, expires_in=3 * 86400))

    assert result.published is True
    assert result.credential_status is CredentialStatus.EXPIRING_SOON
    assert result.expiry_warning is not None
    assert "expires on" in result.expiry_warning


# --- the credential gates the publish ---------------------------------------

def test_a_missing_credential_fails_before_any_request(tmp_path):
    transport = FakeTransport()
    result = publish(transport, tmp_path / "absent.json")

    assert transport.calls == []
    assert result.outcome is PublicationOutcome.FAILED
    assert result.error_category is LinkedInErrorCategory.AUTHENTICATION
    assert result.requires_human_intervention is True
    assert result.retryable is False
    assert result.credential_status is CredentialStatus.MISSING


def test_an_expired_credential_requires_a_human_and_is_not_retried(tmp_path):
    """PLAN.md §11: this terminates as REQUIRES_HUMAN_INTERVENTION."""
    transport = FakeTransport()
    result = publish(transport, credentialed(tmp_path, expires_in=-3600))

    assert transport.calls == []
    assert result.outcome is PublicationOutcome.FAILED
    assert result.error_category is LinkedInErrorCategory.AUTHENTICATION
    assert result.requires_human_intervention is True
    assert result.retryable is False
    assert result.credential_status is CredentialStatus.EXPIRED


def test_an_unreadable_credential_is_an_authentication_failure(tmp_path):
    path = tmp_path / "linkedin_tokens.json"
    path.write_text("{ this is not json", encoding="utf-8")
    transport = FakeTransport()
    result = publish(transport, path)

    assert transport.calls == []
    assert result.error_category is LinkedInErrorCategory.AUTHENTICATION
    assert result.credential_status is CredentialStatus.UNREADABLE


def test_an_expiring_credential_still_publishes(tmp_path):
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish(transport, credentialed(tmp_path, expires_in=2 * 86400))
    assert result.published is True


# --- validation --------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_text_is_a_validation_failure_with_no_request(tmp_path, text):
    transport = FakeTransport()
    result = publish(transport, credentialed(tmp_path), text=text)

    assert transport.calls == []
    assert result.outcome is PublicationOutcome.FAILED
    assert result.error_category is LinkedInErrorCategory.VALIDATION
    assert result.requires_human_intervention is False
    assert result.published is False


def test_oversized_text_is_rejected_without_a_request(tmp_path):
    transport = FakeTransport()
    result = publish(transport,
                     credentialed(tmp_path),
                     text="x" * (config.LINKEDIN_MAX_COMMENTARY_CHARS + 1))

    assert transport.calls == []
    assert result.error_category is LinkedInErrorCategory.VALIDATION


# --- every error category, from a simulated response -------------------------

@pytest.mark.parametrize("status, category, retryable, human", [
    (401, LinkedInErrorCategory.AUTHENTICATION, False, True),
    (403, LinkedInErrorCategory.PERMISSION, False, True),
    (400, LinkedInErrorCategory.VALIDATION, False, False),
    (422, LinkedInErrorCategory.VALIDATION, False, False),
    (404, LinkedInErrorCategory.UNKNOWN, False, True),
    (429, LinkedInErrorCategory.RATE_LIMIT, True, False),
])
def test_a_rejected_post_is_classified_and_never_claimed_as_published(
        tmp_path, status, category, retryable, human):
    transport = FakeTransport(
        userinfo=identity(),
        post=response(status, body=json.dumps({"message": "no"})),
    )
    result = publish(transport, credentialed(tmp_path))

    assert result.published is False
    assert result.post_id is None
    assert result.outcome is PublicationOutcome.FAILED  # a reply *was* received
    assert result.error_category is category
    assert result.retryable is retryable
    assert result.requires_human_intervention is human
    assert result.http_status == status


@pytest.mark.parametrize("status", [500, 503])
def test_a_post_request_that_fails_with_5xx_is_ambiguous_not_a_failure(
        tmp_path, status):
    """The request reached LinkedIn, so "no post exists" cannot be claimed.

    A 5xx is LinkedIn's own handling failing after it received the request.
    Nothing here can establish that the post was not created, and reporting
    ``FAILED`` would release the content: Step 6 protects text from being sent
    twice only while its intent is unresolved, so a wrong ``FAILED`` is how
    the same post goes out again on a later run.
    """
    transport = FakeTransport(userinfo=identity(),
                              post=response(status, body="boom"))
    result = publish(transport, credentialed(tmp_path))

    assert result.outcome is PublicationOutcome.UNKNOWN
    assert result.ambiguous is True
    assert result.published is False
    assert result.post_id is None
    assert result.http_status == status
    assert result.error_category is LinkedInErrorCategory.TRANSPORT
    # The *failure* is transient, which is what `retryable` is advice about;
    # the *outcome* is what is unknown, and Step 6 never retries either way.
    assert result.retryable is True
    assert result.requires_human_intervention is False


@pytest.mark.parametrize("status", [500, 503])
def test_a_failed_identity_lookup_stays_a_failure(tmp_path, status):
    """No post request has been made yet, so no post can exist.

    The 5xx rule is about the post request. Treating the identity lookup the
    same way would block content that was never sent.
    """
    transport = FakeTransport(userinfo=response(status, body="boom"),
                              post=published())
    result = publish(transport, credentialed(tmp_path))

    assert result.outcome is PublicationOutcome.FAILED
    assert result.ambiguous is False
    assert [call.method for call in transport.calls] == ["GET"], (
        "an identity failure must not reach the post endpoint"
    )


def test_a_rejected_post_keeps_the_response_body_for_diagnosis(tmp_path):
    transport = FakeTransport(
        userinfo=identity(),
        post=response(422, body=json.dumps({"message": "commentary too long"})),
    )
    result = publish(transport, credentialed(tmp_path))
    assert "commentary too long" in result.response_body


def test_a_refused_identity_lookup_fails_without_attempting_the_post(
        tmp_path):
    transport = FakeTransport(userinfo=response(403, body="forbidden"))
    result = publish(transport, credentialed(tmp_path))

    assert [call.url for call in transport.calls] == [USERINFO_URL]
    assert result.error_category is LinkedInErrorCategory.PERMISSION
    assert result.requires_human_intervention is True


def test_an_identity_response_without_a_member_id_publishes_nothing(tmp_path):
    transport = FakeTransport(userinfo=response(200, body=json.dumps({})))
    result = publish(transport, credentialed(tmp_path))

    assert [call.url for call in transport.calls] == [USERINFO_URL]
    assert result.published is False
    assert result.outcome is PublicationOutcome.FAILED
    assert result.post_id is None


# --- ambiguity: the case the design exists for -------------------------------

def test_a_success_without_a_post_id_is_ambiguous_not_published(tmp_path):
    """Accepted but unevidenced. LinkedIn offers no read-back to resolve it."""
    transport = FakeTransport(userinfo=identity(), post=response(201))
    result = publish(transport, credentialed(tmp_path))

    assert result.published is False
    assert result.ambiguous is True
    assert result.outcome is PublicationOutcome.UNKNOWN
    assert result.post_id is None
    assert result.retryable is False  # retrying could duplicate the post


@pytest.mark.parametrize("exc", [
    requests.exceptions.ReadTimeout("no answer"),
    requests.exceptions.ConnectionError("connection aborted"),
])
def test_a_transport_failure_after_sending_is_ambiguous(tmp_path, exc):
    transport = FakeTransport(userinfo=identity(), post=exc)
    result = publish(transport, credentialed(tmp_path))

    assert result.ambiguous is True
    assert result.published is False
    assert result.error_category is LinkedInErrorCategory.TRANSPORT
    assert result.retryable is False


def test_a_connect_failure_is_a_definitive_failure(tmp_path):
    """Nothing was sent, so nothing exists and a retry is safe (Step 6)."""
    transport = FakeTransport(
        userinfo=identity(),
        post=requests.exceptions.ConnectTimeout("timed out"),
    )
    result = publish(transport, credentialed(tmp_path))

    assert result.outcome is PublicationOutcome.FAILED
    assert result.ambiguous is False
    assert result.error_category is LinkedInErrorCategory.TRANSPORT
    assert result.retryable is True


def test_a_timeout_on_the_identity_lookup_is_ambiguous_for_the_post(tmp_path):
    transport = FakeTransport(
        userinfo=requests.exceptions.ReadTimeout("no answer"))
    result = publish(transport, credentialed(tmp_path))
    assert result.outcome is PublicationOutcome.UNKNOWN


# --- refusal to leak, refusal to prompt --------------------------------------

def test_no_token_value_appears_in_a_result(tmp_path):
    """Acceptance criterion: no token in logs, errors, or results."""
    transport = FakeTransport(
        userinfo=response(
            # A response body that echoes the token, as a diagnostic might.
            401, body=json.dumps({"message": f"bad token {TOKEN}"}),
        ),
    )
    result = publish(transport, credentialed(tmp_path))

    rendered = repr(result) + result.message + (result.response_body or "")
    assert TOKEN not in rendered
    assert "[REDACTED]" in result.response_body


def test_the_publish_path_cannot_prompt_or_print():
    """An unattended workflow cannot block on input, and results are the
    interface — not stdout (PLAN.md Step 5, acceptance criteria)."""
    package = paths.PROJECT_ROOT / "app" / "integrations" / "linkedin"
    for module in package.glob("*.py"):
        source = module.read_text()
        assert "input(" not in source, f"{module.name} prompts"
        assert "print(" not in source, f"{module.name} prints"


def test_publishing_never_writes_anything_but_the_credential_expiry(
        tmp_path, state_store):
    """Step 5 stores nothing about the publication; Step 6 owns that."""
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish_to_linkedin(
        TEXT,
        client=LinkedInClient(get=transport.get, post=transport.post),
        token_path=credentialed(tmp_path),
        store=state_store,
        now=NOW,
    )

    assert result.published is True
    assert state_store.get_credential_expiry(CREDENTIAL_NAME) is not None
    assert state_store.list_publications() == []
    assert state_store.list_publish_intents() == []
    assert state_store.list_runs() == []
    assert state_store.list_failures() == []


def test_the_expiry_is_recorded_even_when_the_publish_fails(tmp_path,
                                                            state_store):
    transport = FakeTransport(userinfo=identity(),
                              post=response(500, body="boom"))
    publish_to_linkedin(TEXT,
                        client=LinkedInClient(get=transport.get,
                                              post=transport.post),
                        token_path=credentialed(tmp_path),
                        store=state_store, now=NOW)
    assert state_store.get_credential_expiry(CREDENTIAL_NAME) is not None


def test_a_store_failure_stops_the_publish_before_any_request(tmp_path):
    """Fail closed: no store, no publish (PLAN.md §11, note on (4))."""
    class Broken:
        def record_credential_expiry(self, **kwargs):
            raise StateStoreError("the store is unavailable")

    transport = FakeTransport(userinfo=identity(), post=published())
    with pytest.raises(StateStoreError):
        publish_to_linkedin(
            TEXT,
            client=LinkedInClient(get=transport.get, post=transport.post),
            token_path=credentialed(tmp_path),
            store=Broken(),
            now=NOW,
        )
    assert transport.calls == []


def test_publishing_works_from_any_working_directory(tmp_path, monkeypatch):
    """Acceptance criterion: the service works from any working directory.

    Nothing on the path may resolve relative to the process's CWD — the token
    path, the configuration, and the .env all come from the project root.
    """
    monkeypatch.chdir(tmp_path)
    transport = FakeTransport(userinfo=identity(), post=published())
    result = publish(transport, credentialed(tmp_path))

    assert result.published is True
    assert result.api_version == config.LINKEDIN_API_VERSION
    assert paths.LINKEDIN_TOKEN_FILE.is_absolute()
    assert paths.ENV_FILE.is_absolute()
