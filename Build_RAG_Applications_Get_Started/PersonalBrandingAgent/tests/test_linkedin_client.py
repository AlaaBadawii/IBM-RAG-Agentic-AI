"""Step 5: the classification table, the client, and the request contract.

Every test here runs offline. The transport is injected, so these exercise the
real request construction — URLs, headers, payload, timeout — against a fake
socket rather than mocking the client's own methods away.

The classification tests are the ones that matter most: they are the only
thing standing between an ambiguous failure and a duplicate post.
"""
import json

import pytest
import requests

from app import config
from app.integrations.linkedin.classification import (
    classify_status,
    classify_transport_error,
    validate_commentary,
)
from app.integrations.linkedin.client import (
    POSTS_URL,
    USERINFO_URL,
    LinkedInClient,
    build_post_payload,
    person_urn_from_userinfo,
    post_id_from_response,
)
from app.integrations.linkedin.enums import (
    LinkedInErrorCategory,
    PublicationOutcome,
)


class RecordedCall:
    """One call the fake transport received."""

    def __init__(self, method: str, url: str, kwargs: dict):
        self.method = method
        self.url = url
        self.kwargs = kwargs

    @property
    def headers(self) -> dict:
        return self.kwargs["headers"]

    @property
    def timeout(self):
        return self.kwargs.get("timeout")


class FakeTransport:
    """A transport that answers with queued responses and records the calls."""

    def __init__(self, *responses, raises: Exception | None = None):
        self.responses = list(responses)
        self.raises = raises
        self.calls: list[RecordedCall] = []

    def _answer(self, method: str, url: str, kwargs: dict):
        self.calls.append(RecordedCall(method, url, kwargs))
        if self.raises is not None:
            raise self.raises
        if not self.responses:
            raise AssertionError(f"unexpected {method} {url}: no response queued")
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._answer("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._answer("POST", url, kwargs)


def response(status: int, *, body: str = "", headers: dict | None = None):
    """A real ``requests.Response`` — the type the client actually handles."""
    built = requests.Response()
    built.status_code = status
    built._content = body.encode("utf-8")
    built.headers.update(headers or {})
    return built


def json_response(status: int, payload: dict):
    return response(status, body=json.dumps(payload),
                    headers={"Content-Type": "application/json"})


def client_for(transport: FakeTransport, **kwargs) -> LinkedInClient:
    return LinkedInClient(get=transport.get, post=transport.post, **kwargs)


# --- the classification table ------------------------------------------------

@pytest.mark.parametrize("status, category, retryable, human", [
    # An expired or revoked credential: only a person can fix it, and
    # re-sending cannot help.
    (401, LinkedInErrorCategory.AUTHENTICATION, False, True),
    # Authenticated but not permitted (missing scope / capability).
    (403, LinkedInErrorCategory.PERMISSION, False, True),
    # LinkedIn understood the request and rejected the post itself.
    (400, LinkedInErrorCategory.VALIDATION, False, False),
    (422, LinkedInErrorCategory.VALIDATION, False, False),
    # A retired or missing endpoint: a version problem, not a post problem.
    (404, LinkedInErrorCategory.UNKNOWN, False, True),
    # An explicit backoff signal.
    (429, LinkedInErrorCategory.RATE_LIMIT, True, False),
    # LinkedIn's own failure, after receiving the request.
    (500, LinkedInErrorCategory.TRANSPORT, True, False),
    (503, LinkedInErrorCategory.TRANSPORT, True, False),
])
def test_every_status_maps_to_the_documented_category(
        status, category, retryable, human):
    classification = classify_status(status)
    assert classification.category is category
    assert classification.retryable is retryable
    assert classification.requires_human_intervention is human


def test_rate_limit_and_server_errors_are_the_only_retryable_ones():
    """Retryability is advice, so it must stay narrow and explainable."""
    retryable = {
        status for status in (400, 401, 403, 404, 409, 422, 429, 500, 503, 302)
        if classify_status(status).retryable
    }
    assert retryable == {429, 500, 503}


def test_a_connect_failure_proves_nothing_was_published():
    """The socket never opened, so no post can exist and a retry is safe."""
    for exc in (requests.exceptions.ConnectTimeout("timed out"),
                requests.exceptions.SSLError("handshake failed")):
        classification, outcome = classify_transport_error(exc)
        assert classification.category is LinkedInErrorCategory.TRANSPORT
        assert classification.retryable is True
        assert outcome is PublicationOutcome.FAILED


@pytest.mark.parametrize("exc", [
    requests.exceptions.ReadTimeout("no answer"),
    requests.exceptions.ConnectionError("connection aborted"),
    requests.exceptions.ChunkedEncodingError("truncated"),
    requests.exceptions.RequestException("something else"),
])
def test_a_failure_after_sending_is_ambiguous_never_failed(exc):
    """The request may have been processed; the outcome must say so.

    Reporting these as FAILED would let the next run publish a duplicate.
    """
    classification, outcome = classify_transport_error(exc)
    assert classification.category is LinkedInErrorCategory.TRANSPORT
    assert classification.retryable is False
    assert outcome is PublicationOutcome.UNKNOWN


# --- local validation --------------------------------------------------------

def test_empty_and_whitespace_text_is_rejected_locally():
    assert validate_commentary("", max_chars=3000) is not None
    assert validate_commentary("   \n\t ", max_chars=3000) is not None
    assert validate_commentary("hello", max_chars=3000) is None


def test_oversized_text_is_rejected_with_its_actual_length():
    reason = validate_commentary("x" * 3001, max_chars=3000)
    assert reason is not None and "3001" in reason and "3000" in reason
    assert validate_commentary("x" * 3000, max_chars=3000) is None


# --- request construction ----------------------------------------------------

def test_every_request_carries_a_bounded_timeout():
    """No call may be made without a timeout, on either endpoint."""
    transport = FakeTransport(
        json_response(200, {"sub": "abc"}),
        response(201, headers={"x-restli-id": "urn:li:share:1"}),
    )
    client = client_for(transport, timeout=12.5)
    client.fetch_person_urn("token-value")
    client.create_post("token-value", "urn:li:person:abc", "hello")

    assert [call.timeout for call in transport.calls] == [12.5, 12.5]
    assert all(call.timeout is not None for call in transport.calls)


def test_the_default_timeout_comes_from_configuration():
    client = LinkedInClient()
    assert client.timeout == config.LINKEDIN_TIMEOUT_SECONDS
    assert client.timeout > 0


def test_a_client_cannot_be_built_with_an_unbounded_timeout():
    with pytest.raises(ValueError):
        LinkedInClient(timeout=0)
    with pytest.raises(ValueError):
        LinkedInClient(timeout=-1)


def test_the_api_version_is_configuration_and_travels_in_the_header():
    """The version is a value, not a literal buried in a header dict."""
    client = LinkedInClient(api_version="203012")
    assert client.api_version == "203012"
    assert client._headers("token", json_body=True)["LinkedIn-Version"] == "203012"


def test_requests_use_the_documented_endpoints_headers_and_payload():
    transport = FakeTransport(
        json_response(200, {"sub": "abc"}),
        response(201, headers={"x-restli-id": "urn:li:share:1"}),
    )
    client = client_for(transport, api_version="202607")
    client.fetch_person_urn("token-value")
    client.create_post("token-value", "urn:li:person:abc", "hello world")

    userinfo, posts = transport.calls
    assert (userinfo.method, userinfo.url) == ("GET", USERINFO_URL)
    assert (posts.method, posts.url) == ("POST", POSTS_URL)
    assert posts.headers["Authorization"] == "Bearer token-value"
    assert posts.headers["LinkedIn-Version"] == "202607"
    assert posts.headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert posts.headers["Content-Type"] == "application/json"
    assert posts.kwargs["json"] == build_post_payload("urn:li:person:abc",
                                                      "hello world")
    assert posts.kwargs["json"]["lifecycleState"] == "PUBLISHED"
    assert posts.kwargs["json"]["visibility"] == "PUBLIC"


def test_the_client_retains_no_token_after_a_call():
    """A client may outlive one attempt; it must not outlive its secret."""
    transport = FakeTransport(
        json_response(200, {"sub": "abc"}),
        response(201, headers={"x-restli-id": "urn:li:share:1"}),
    )
    client = client_for(transport, api_version="202607")
    client.fetch_person_urn("super-secret-token")
    client.create_post("super-secret-token", "urn:li:person:abc", "hello")
    assert "super-secret-token" not in repr(vars(client))


# --- response helpers --------------------------------------------------------

def test_person_urn_is_built_from_the_subject():
    assert person_urn_from_userinfo({"sub": "abc123"}) == "urn:li:person:abc123"


@pytest.mark.parametrize("payload", [
    None, {}, {"sub": ""}, {"sub": "   "}, {"sub": 42}, "not-a-mapping",
])
def test_an_unidentifiable_response_yields_no_urn(payload):
    assert person_urn_from_userinfo(payload) is None


def test_post_id_is_read_from_the_restli_header():
    assert post_id_from_response(
        response(201, headers={"x-restli-id": "urn:li:share:7"})
    ) == "urn:li:share:7"


@pytest.mark.parametrize("headers", [{}, {"x-restli-id": ""},
                                     {"x-restli-id": "   "}])
def test_a_response_without_a_post_id_yields_none(headers):
    assert post_id_from_response(response(201, headers=headers)) is None
