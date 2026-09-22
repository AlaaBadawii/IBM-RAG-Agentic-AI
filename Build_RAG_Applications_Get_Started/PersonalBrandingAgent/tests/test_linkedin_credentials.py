"""Step 5: the credential lifecycle.

The questions an unattended run has to answer before it publishes: is there a
credential, when does it die, and what happens when it does. Every test builds
its own token file under ``tmp_path`` — none reads, writes, or depends on the
real credential in ``Auth_handling/``.
"""
import base64
import json
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

from app import config, paths
from app.errors import StateStoreError
from app.integrations.linkedin.credentials import (
    CREDENTIAL_NAME,
    check_credential,
    evaluate_credential,
    load_credential,
    record_expiry,
)
from app.integrations.linkedin.enums import CredentialStatus
from app.integrations.linkedin.errors import CredentialError
from app.state.enums import CredentialDerivation
from app.state.models import to_iso

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
TOKEN = "fake-access-token-value"


def _normalized(expression: str) -> str:
    """An expression as ``ast.unparse`` renders it, so quoting cannot matter."""
    import ast

    return ast.unparse(ast.parse(expression, mode="eval").body)


def id_token(issued_at: datetime, *, claims_extra: dict | None = None) -> str:
    """A structurally real JWT with the claims that matter to us."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=")
    claims = {"iat": int(issued_at.timestamp()), "sub": "abc",
              **(claims_extra or {})}
    payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode()
    ).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.signature"


@pytest.fixture
def token_file(tmp_path):
    """Factory for a credential file, written with chosen contents."""
    def _write(*, expires_in=5183999, issued_at=NOW, id_token_value="auto",
               refresh_token=None, access_token=TOKEN, **extra):
        written = NOW if issued_at is None else issued_at
        if id_token_value == "auto":
            id_token_value = id_token(written) if written is not None else None
        payload = {
            "access_token": access_token,
            "expires_in": expires_in,
            "scope": "email,openid,profile,w_member_social",
            "token_type": "Bearer",
        }
        if id_token_value is not None:
            payload["id_token"] = id_token_value
        if refresh_token is not None:
            payload["refresh_token"] = refresh_token
        payload.update(extra)
        path = tmp_path / "linkedin_tokens.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        if written is not None:
            stamp = written.timestamp()
            os.utime(path, (stamp, stamp))
        return path
    return _write


class Recorder:
    """A fake transport that records its calls and answers once."""

    def __init__(self, response=None, raises: Exception | None = None):
        self.response = response
        self.raises = raises
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.raises is not None:
            raise self.raises
        return self.response


def token_response(payload: dict):
    built = requests.Response()
    built.status_code = 200
    built._content = json.dumps(payload).encode()
    return built


# --- reading the credential --------------------------------------------------

def test_expiry_is_derived_from_the_signed_issuance_claim(token_file):
    """The credential itself says when it was issued; that is the truth."""
    path = token_file(expires_in=3600)
    credential = load_credential(path)

    assert credential.issuance_evidence is CredentialDerivation.ID_TOKEN_IAT
    assert credential.issued_at == to_iso(NOW)
    assert credential.expires_at == to_iso(NOW + timedelta(seconds=3600))
    assert credential.has_refresh_token is False


def test_expiry_falls_back_to_the_file_mtime_without_an_id_token(token_file):
    """The exchange that issues the token is what writes the file."""
    path = token_file(expires_in=7200, id_token_value=None)
    credential = load_credential(path)

    assert credential.issuance_evidence is CredentialDerivation.FILE_MTIME
    assert credential.issued_at == credential.source_mtime
    assert credential.expires_at == to_iso(NOW + timedelta(seconds=7200))


def test_an_undecodable_id_token_falls_back_rather_than_failing(token_file):
    for broken in ("not-a-jwt", "a.!!!.c", "a.b.c"):
        credential = load_credential(token_file(id_token_value=broken,
                                                expires_in=3600))
        assert credential.issuance_evidence is CredentialDerivation.FILE_MTIME


def test_an_unknown_expiry_is_reported_as_unknown_never_guessed(token_file):
    path = token_file(expires_in=None, id_token_value=None)
    credential = load_credential(path)
    report = evaluate_credential(credential, now=NOW)

    assert credential.expires_at is None
    assert credential.issuance_evidence is None
    # Usable, because nothing says it is not — but with no expiry warning,
    # which the report says out loud rather than inventing a date.
    assert report.status is CredentialStatus.VALID
    assert report.days_remaining is None
    assert "unknown" in report.message


def test_a_missing_file_is_reported_not_raised(tmp_path):
    report = check_credential(path=tmp_path / "absent.json", now=NOW)
    assert report.status is CredentialStatus.MISSING
    assert report.usable is False
    assert report.requires_human is True
    assert "linkedin_oauth_setup.py" in report.message


@pytest.mark.parametrize("body", ["not json at all", "[1, 2, 3]", "{}",
                                  '{"access_token": ""}'])
def test_an_unusable_file_is_reported_not_raised(tmp_path, body):
    path = tmp_path / "tokens.json"
    path.write_text(body, encoding="utf-8")
    report = check_credential(path=path, now=NOW)
    assert report.status is CredentialStatus.UNREADABLE
    assert report.requires_human is True
    assert report.usable is False


def test_load_credential_raises_only_credential_errors(tmp_path):
    with pytest.raises(CredentialError):
        load_credential(tmp_path / "absent.json")


def test_the_credential_never_renders_its_own_secrets(token_file):
    credential = load_credential(token_file(refresh_token="refresh-secret"))
    assert TOKEN not in repr(credential)
    assert "refresh-secret" not in repr(credential)
    assert credential.redact(f"leaked {TOKEN} and refresh-secret") == (
        "leaked [REDACTED] and [REDACTED]"
    )


# --- the lifecycle decision --------------------------------------------------

def test_a_healthy_credential_is_valid(token_file):
    report = evaluate_credential(load_credential(token_file(expires_in=5183999)),
                                 now=NOW)
    assert report.status is CredentialStatus.VALID
    assert report.days_remaining == pytest.approx(59.99, abs=0.1)
    assert report.usable is True


def test_an_approaching_expiry_warns_before_it_fails(token_file):
    """The warning exists so a person can act while the system still works."""
    path = token_file(expires_in=5 * 86400)
    report = evaluate_credential(load_credential(path), now=NOW)

    assert report.status is CredentialStatus.EXPIRING_SOON
    assert report.usable is True          # still publishing, not yet broken
    assert report.requires_human is False  # not a failure, a warning
    assert report.days_remaining == pytest.approx(5.0, abs=0.01)
    assert "expires on" in report.message
    assert "linkedin_oauth_setup.py" in report.message


def test_expiry_is_a_clear_authentication_state_not_a_generic_error(token_file):
    report = evaluate_credential(load_credential(token_file(expires_in=-60)),
                                 now=NOW)
    assert report.status is CredentialStatus.EXPIRED
    assert report.usable is False
    assert report.requires_human is True
    assert "expired" in report.message


def test_the_warning_window_is_configuration(token_file):
    credential = load_credential(token_file(expires_in=20 * 86400))
    assert evaluate_credential(credential, now=NOW,
                               warning_days=30).status is (
        CredentialStatus.EXPIRING_SOON)
    assert evaluate_credential(credential, now=NOW,
                               warning_days=1).status is CredentialStatus.VALID


# --- refresh -----------------------------------------------------------------

def test_no_refresh_is_attempted_when_none_is_available(token_file):
    """The documented state of the real credential (PLAN.md §5.2)."""
    send = Recorder()
    report = check_credential(path=token_file(expires_in=-60), now=NOW,
                              post=send)

    assert send.calls == []
    assert report.status is CredentialStatus.EXPIRED


def test_an_expired_credential_with_a_refresh_token_is_refreshed(token_file):
    path = token_file(expires_in=-60, refresh_token="the-refresh-token",
                      id_token_value=None)
    fresh = id_token(NOW)
    send = Recorder(token_response(
        {"access_token": "a-new-access-token", "expires_in": 5183999,
         "id_token": fresh}
    ))
    report = check_credential(path=path, now=NOW, post=send)

    assert len(send.calls) == 1
    assert send.calls[0]["data"]["grant_type"] == "refresh_token"
    assert send.calls[0]["data"]["refresh_token"] == "the-refresh-token"
    assert send.calls[0]["timeout"] == config.LINKEDIN_TIMEOUT_SECONDS
    assert report.status is CredentialStatus.VALID
    assert report.credential.access_token == "a-new-access-token"
    # The new token is persisted, or the next run would refresh again.
    assert json.loads(path.read_text())["access_token"] == "a-new-access-token"


def test_a_refresh_that_is_rejected_stays_an_authentication_failure(token_file):
    path = token_file(expires_in=-60, refresh_token="the-refresh-token")
    rejected = requests.Response()
    rejected.status_code = 400
    report = check_credential(path=path, now=NOW, post=Recorder(rejected))

    assert report.status is CredentialStatus.EXPIRED
    assert report.requires_human is True
    # The old credential is left untouched: a failed refresh must not
    # destroy the token that is still on disk.
    assert json.loads(path.read_text())["access_token"] == TOKEN


def test_a_refresh_that_times_out_is_not_retried(token_file):
    path = token_file(expires_in=-60, refresh_token="the-refresh-token")
    send = Recorder(raises=requests.exceptions.ReadTimeout("no answer"))
    report = check_credential(path=path, now=NOW, post=send)

    assert len(send.calls) == 1  # attempted once, never retried here
    assert report.status is CredentialStatus.EXPIRED


def test_a_refresh_without_application_credentials_is_not_attempted(
        token_file, monkeypatch):
    monkeypatch.setattr(config, "LINKEDIN_CLIENT_ID", "")
    monkeypatch.setattr(config, "LINKEDIN_CLIENT_SECRET", "")
    send = Recorder()
    report = check_credential(
        path=token_file(expires_in=-60, refresh_token="the-refresh-token"),
        now=NOW, post=send)

    assert send.calls == []
    assert report.status is CredentialStatus.EXPIRED


def test_a_valid_credential_is_never_refreshed_pre_emptively(token_file):
    """An unverified refresh path is not worth trading a warning for."""
    send = Recorder()
    report = check_credential(
        path=token_file(expires_in=5 * 86400, refresh_token="a-refresh-token"),
        now=NOW, post=send)

    assert send.calls == []
    assert report.status is CredentialStatus.EXPIRING_SOON


# --- recording the expiry ----------------------------------------------------

def test_the_expiry_is_recorded_in_operational_state(state_store, token_file):
    check_credential(path=token_file(expires_in=3600), store=state_store,
                     now=NOW)

    recorded = state_store.get_credential_expiry(CREDENTIAL_NAME)
    assert recorded is not None
    assert recorded.expires_at == to_iso(NOW + timedelta(seconds=3600))
    assert recorded.issued_at == to_iso(NOW)
    assert recorded.derived_from is CredentialDerivation.ID_TOKEN_IAT


def test_recording_twice_updates_one_row_never_accumulates(
        state_store, token_file):
    check_credential(path=token_file(expires_in=3600), store=state_store,
                     now=NOW)
    check_credential(path=token_file(expires_in=7200), store=state_store,
                     now=NOW)

    rows = state_store.list_credential_expiries()
    assert len(rows) == 1
    assert rows[0].expires_at == to_iso(NOW + timedelta(seconds=7200))


def test_the_mtime_fallback_is_recorded_as_such(state_store, token_file):
    check_credential(path=token_file(expires_in=3600, id_token_value=None),
                     store=state_store, now=NOW)
    recorded = state_store.get_credential_expiry(CREDENTIAL_NAME)
    assert recorded.derived_from is CredentialDerivation.FILE_MTIME


def test_an_unknown_expiry_records_nothing(state_store, token_file):
    check_credential(path=token_file(expires_in=None, id_token_value=None),
                     store=state_store, now=NOW)
    assert state_store.list_credential_expiries() == []


def test_a_missing_credential_records_nothing_and_does_not_raise(
        state_store, tmp_path):
    report = check_credential(path=tmp_path / "absent.json",
                              store=state_store, now=NOW)
    assert report.status is CredentialStatus.MISSING
    assert state_store.list_credential_expiries() == []


def test_a_store_failure_is_never_swallowed(state_store, token_file):
    """A run that cannot record what it observed must not go on to publish."""
    class Broken:
        def record_credential_expiry(self, **kwargs):
            raise StateStoreError("the store is unavailable")

    with pytest.raises(StateStoreError):
        check_credential(path=token_file(expires_in=3600), store=Broken(),
                         now=NOW)


def test_record_expiry_is_a_no_op_without_a_store(token_file):
    report = evaluate_credential(load_credential(token_file()), now=NOW)
    record_expiry(None, report)  # must not raise


# --- the paths themselves ----------------------------------------------------

def test_the_token_path_is_defined_once_and_is_absolute():
    assert paths.LINKEDIN_TOKEN_FILE.is_absolute()
    assert paths.LINKEDIN_TOKEN_FILE.name == "linkedin_tokens.json"
    assert paths.LINKEDIN_TOKEN_FILE.parent.name == "Auth_handling"
    assert paths.ENV_FILE == paths.PROJECT_ROOT / ".env"


def test_the_scripts_resolve_the_same_token_file_the_application_does():
    """The defect this step exists to fix, kept fixed by a test.

    The OAuth script *creates* the token and the two readers consume it. If
    any of them resolves a different file, the token is written somewhere
    nothing looks — which is exactly what happened before Step 5.
    """
    import ast

    expected = paths.LINKEDIN_TOKEN_FILE
    scripts = ["linkedin_oauth_setup.py", "test_credentials.py", "test_post.py"]
    for name in scripts:
        source = (paths.PROJECT_ROOT / "Auth_handling" / name).read_text()
        tree = ast.parse(source)
        assignments = {
            target.id: ast.unparse(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        assert assignments.get("TOKEN_FILE") == _normalized(
            'Path(__file__).parent / "linkedin_tokens.json"'
        ), f"{name} must resolve the token file relative to itself"
        # Resolved relative to the script's own directory == the app's path.
        assert (expected.parent / "linkedin_tokens.json") == expected


def test_every_script_loads_the_env_file_by_path():
    """`load_dotenv()` with no argument reads the current directory's .env."""
    import ast

    for name in ("linkedin_oauth_setup.py", "test_credentials.py",
                 "test_post.py"):
        source = (paths.PROJECT_ROOT / "Auth_handling" / name).read_text()
        calls = [node for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Call)
                 and getattr(node.func, "id", None) == "load_dotenv"]
        assert calls, f"{name} no longer loads .env at all"
        assert all(call.args or call.keywords for call in calls), (
            f"{name} calls load_dotenv() with no path, so it reads whatever "
            f".env happens to be in the current directory"
        )


def test_the_real_credential_is_never_committed_or_required():
    """The integration must not depend on a credential being in the tree."""
    assert paths.LINKEDIN_TOKEN_FILE.name in (
        paths.PROJECT_ROOT / ".gitignore"
    ).read_text()
