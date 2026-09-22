"""Step 7: the SMTP transport — configuration, TLS, and bounded failure.

No test here opens a socket. ``smtplib``'s client classes are replaced with a
recording fake, so what is asserted is exactly what the real call would do:
which host and port, with which timeout, whether STARTTLS or implicit TLS was
used, whether login happened — and what a failure of each kind becomes.

That last part is the point of the transport existing at all: ``smtplib``
raises six ways for six different reasons, and the notification layer has to
tell a person which one it was without leaking the password into the telling.
"""
import smtplib
from types import SimpleNamespace

import pytest

from app import config as app_config
from app.errors import ConfigError
from app.notify import (
    NotificationFailureCategory,
    NotificationMessage,
    NotificationService,
    SMTPConfig,
    SMTPTransport,
    missing_settings,
    smtp_config,
)
from app.notify import transport as transport_module
from app.notify.errors import (
    NotificationConfigurationError,
    NotificationDeliveryError,
)

PASSWORD = "app-password-xyz"
SUMMARY = "SMTP is a decision, not a preference (PLAN.md §12.1)."


def a_config(**overrides) -> SMTPConfig:
    values = dict(
        host="smtp.example.com", port=587, sender="owner@example.com",
        recipient="owner@example.com", username="owner@example.com",
        password=PASSWORD, timeout=7.5,
    )
    values.update(overrides)
    return SMTPConfig(**values)


def a_message() -> NotificationMessage:
    return NotificationMessage(subject="[PersonalBrandingAgent] test",
                               body=SUMMARY)


@pytest.fixture
def smtp(monkeypatch):
    """Recording fakes in place of ``smtplib.SMTP`` / ``SMTP_SSL``."""
    created: list = []

    class FakeSMTP:
        fail_connect: BaseException | None = None
        fail_login: BaseException | None = None
        fail_send: BaseException | None = None

        def __init__(self, host, port, timeout=None, context=None):
            self.host, self.port, self.timeout = host, port, timeout
            self.context = context
            self.operations: list[tuple] = []
            self.payload = None
            if FakeSMTP.fail_connect is not None:
                raise FakeSMTP.fail_connect
            created.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self.operations.append(("closed",))
            return False

        def starttls(self, context=None):
            self.operations.append(("starttls", context is not None))

        def login(self, username, password):
            self.operations.append(("login", username, password))
            if FakeSMTP.fail_login is not None:
                raise FakeSMTP.fail_login

        def send_message(self, payload):
            self.operations.append(("send_message", payload))
            self.payload = payload
            if FakeSMTP.fail_send is not None:
                raise FakeSMTP.fail_send

    class FakeSMTPSSL(FakeSMTP):
        pass

    monkeypatch.setattr(transport_module.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(transport_module.smtplib, "SMTP_SSL", FakeSMTPSSL)
    return SimpleNamespace(clients=created, SMTP=FakeSMTP, SMTP_SSL=FakeSMTPSSL)


def configure(monkeypatch, **values):
    """Point ``app.config`` at a working mail configuration."""
    defaults = dict(
        SMTP_HOST="smtp.example.com", SMTP_PORT=587,
        SMTP_SENDER="owner@example.com", SMTP_RECIPIENT="owner@example.com",
        SMTP_USERNAME="owner@example.com", SMTP_PASSWORD=PASSWORD,
        SMTP_TLS="starttls", SMTP_TIMEOUT_SECONDS=7.5,
    )
    defaults.update(values)
    for name, value in defaults.items():
        monkeypatch.setattr(app_config, name, value)
    return defaults


# --- what the connection does ------------------------------------------------

def test_a_notification_is_sent_to_the_configured_addresses(smtp):
    config = a_config()
    SMTPTransport(config).send(a_message())

    client = smtp.clients[0]
    payload = client.payload
    assert payload["From"] == "owner@example.com"
    assert payload["To"] == "owner@example.com"
    assert payload["Subject"] == "[PersonalBrandingAgent] test"
    assert SUMMARY in payload.get_content()
    assert "send_message" in [op[0] for op in client.operations]


def test_the_connection_is_bounded_and_starttls_is_used(smtp):
    config = a_config(tls="starttls")
    SMTPTransport(config).send(a_message())

    client = smtp.clients[0]
    assert (client.host, client.port) == ("smtp.example.com", 587)
    assert client.timeout == 7.5, "an unbounded SMTP connection can hold a run open"
    assert ("starttls", True) in client.operations
    assert ("login", "owner@example.com", PASSWORD) in client.operations
    assert ("closed",) in client.operations


def test_ssl_opens_an_implicitly_encrypted_connection(smtp):
    SMTPTransport(a_config(tls="ssl")).send(a_message())

    clients = smtp.clients
    assert len(clients) == 1
    assert isinstance(clients[0], smtp.SMTP_SSL)
    assert "starttls" not in [op[0] for op in clients[0].operations]


def test_tls_none_does_not_negotiate(smtp):
    SMTPTransport(a_config(tls="none", username="", password="")).send(a_message())

    operations = smtp.clients[0].operations
    assert "starttls" not in [op[0] for op in operations]
    assert "login" not in [op[0] for op in operations]


def test_an_unauthenticated_relay_is_not_asked_to_log_in(smtp):
    SMTPTransport(a_config(username="", password="")).send(a_message())
    assert "login" not in [op[0] for op in smtp.clients[0].operations]


# --- configuration ------------------------------------------------------------

def test_the_settings_come_from_configuration(monkeypatch):
    """Acceptance: SMTP settings and credentials come from configuration only."""
    values = configure(monkeypatch, SMTP_HOST="mail.internal.test",
                       SMTP_PORT=2525, SMTP_RECIPIENT="alerts@internal.test",
                       SMTP_TLS="ssl", SMTP_TIMEOUT_SECONDS=3)

    resolved = SMTPTransport().config
    assert resolved is not None
    assert resolved.host == values["SMTP_HOST"]
    assert resolved.port == values["SMTP_PORT"]
    assert resolved.recipient == values["SMTP_RECIPIENT"]
    assert resolved.tls == values["SMTP_TLS"]
    assert resolved.timeout == values["SMTP_TIMEOUT_SECONDS"]
    assert "mail.internal.test" in SMTPTransport().describe()


def test_a_missing_setting_names_itself(monkeypatch):
    """Acceptance: a missing credential produces a clear configuration error."""
    configure(monkeypatch, SMTP_HOST="", SMTP_SENDER="", SMTP_RECIPIENT="")

    assert missing_settings() == ["SMTP_HOST", "SMTP_SENDER", "SMTP_RECIPIENT"]
    assert smtp_config() is None
    with pytest.raises(ConfigError) as caught:
        from app.notify import require_smtp

        require_smtp()
    assert "SMTP_HOST" in str(caught.value)
    assert "SMTP_RECIPIENT" in str(caught.value)


def test_the_transport_refuses_to_send_without_configuration(monkeypatch, smtp):
    """Misconfiguration fails before a socket is spent on it."""
    configure(monkeypatch, SMTP_HOST="")

    with pytest.raises(NotificationConfigurationError) as caught:
        SMTPTransport().send(a_message())

    assert caught.value.category is NotificationFailureCategory.CONFIGURATION
    assert "SMTP_HOST" in str(caught.value)
    assert smtp.clients == [], "a connection was opened with no configuration"
    assert SMTPTransport().recipient == ""


def test_the_default_service_uses_the_smtp_transport():
    assert NotificationService().transport.name == "smtp"


# --- failures, categorized ----------------------------------------------------

def test_a_rejected_credential_is_an_authentication_failure(smtp, monkeypatch):
    configure(monkeypatch)
    smtp.SMTP.fail_login = smtplib.SMTPAuthenticationError(
        535, f"535 Username and Password not accepted: {PASSWORD}".encode()
    )

    with pytest.raises(NotificationDeliveryError) as caught:
        SMTPTransport(a_config()).send(a_message())

    assert caught.value.category is NotificationFailureCategory.AUTHENTICATION
    assert "SMTPAuthenticationError" in str(caught.value)
    assert PASSWORD not in str(caught.value), "the password reached the error text"
    assert "[REDACTED]" in str(caught.value)


@pytest.mark.parametrize("failure", [
    smtplib.SMTPServerDisconnected("connection reset by peer"),
    smtplib.SMTPConnectError(421, "service not available"),
    smtplib.SMTPRecipientsRefused({"owner@example.com": (550, b"no such user")}),
    ConnectionRefusedError("connection refused"),
    TimeoutError("timed out"),
])
def test_a_transport_problem_is_a_transport_failure(smtp, failure):
    smtp.SMTP.fail_send = failure
    if isinstance(failure, (ConnectionRefusedError, TimeoutError)):
        smtp.SMTP.fail_connect = failure

    with pytest.raises(NotificationDeliveryError) as caught:
        SMTPTransport(a_config()).send(a_message())

    assert caught.value.category is NotificationFailureCategory.TRANSPORT
    assert type(failure).__name__ in str(caught.value)


# --- the secret stays in ------------------------------------------------------

def test_the_password_is_not_in_the_config_repr_or_description():
    config = a_config()
    assert PASSWORD not in repr(config)
    assert PASSWORD not in config.describe()
    assert "smtp.example.com:587" in config.describe()
    assert config.secrets() == (PASSWORD,)
    assert config.redact(f"login failed for {PASSWORD}") == \
        "login failed for [REDACTED]"


def test_an_empty_password_carries_no_secret():
    config = a_config(username="", password="")
    assert config.secrets() == ()
