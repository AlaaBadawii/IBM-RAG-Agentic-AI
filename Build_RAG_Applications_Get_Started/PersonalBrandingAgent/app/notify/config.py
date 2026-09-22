"""SMTP configuration as a value, resolved lazily from configuration.

``PLAN.md`` §12.1 decision 3 fixes the mechanism — SMTP, provider-agnostic at
the interface, configured for Gmail — and Step 7 leaves the *addresses* open
(open item C in §12.2). So nothing here is a constant: the settings live in
:mod:`app.config` (environment variables with empty defaults) and are read
when a delivery is attempted, not when the module is imported.

Two rules this module exists to enforce:

1. **A missing setting is a clear configuration error**, naming the variable
   to set — not a stack trace from deep inside ``smtplib``, and not a silent
   success. A notifier that cannot reach anybody still has to say why.
2. **The password is a secret that does not leave.** It is excluded from
   ``repr`` and available only through :meth:`SMTPConfig.secrets`, so a
   traceback or an f-string cannot print it (the same treatment the LinkedIn
   credential gets, for the same reason).
"""
from dataclasses import dataclass, field
from typing import Any

from app import config as app_config
from app.errors import ConfigError

#: Transport name recorded on every delivery row, so a reader can tell which
#: mechanism produced it. ``notifications.transport`` is not constrained by the
#: schema for this reason: another provider may sit behind the same interface.
TRANSPORT_NAME = "smtp"

TLS_STARTTLS = "starttls"
TLS_SSL = "ssl"
TLS_NONE = "none"

#: Settings without which no delivery can be attempted, and the environment
#: variable each comes from. Ordered as they are read, and used to build the
#: error message, so the names in a failure report are the names to go and set.
REQUIRED_SETTINGS = (
    ("SMTP_HOST", "host"),
    ("SMTP_SENDER", "sender"),
    ("SMTP_RECIPIENT", "recipient"),
)


@dataclass(frozen=True)
class SMTPConfig:
    """Everything needed to send one notification, and nothing more.

    ``password`` is the only secret. It is ``repr=False`` so that a config
    object can be logged, included in an error, or compared in a test failure
    without the credential travelling with it.
    """

    host: str
    port: int
    sender: str
    recipient: str
    username: str = ""
    password: str = field(default="", repr=False)
    tls: str = TLS_STARTTLS
    timeout: float = 30.0

    def secrets(self) -> tuple[str, ...]:
        """Every secret value this configuration carries."""
        return (self.password,) if self.password else ()

    def redact(self, text: str) -> str:
        """Strip this configuration's secrets out of ``text``."""
        from app.logging_config import redact

        return redact(text, *self.secrets())

    def describe(self) -> str:
        """How this configuration is recorded on a delivery row.

        Host, port and TLS mode — **not** the username and not the password.
        A delivery record has to be enough to reproduce a failure, and the
        credentials are not part of that: they are read from configuration
        again, and the ``notifications`` table is not a place to copy them
        into (the same reason the message body is not stored there).
        """
        return f"{TRANSPORT_NAME} {self.host}:{self.port} tls={self.tls}"


def _configured_values() -> dict[str, Any]:
    """Read the settings that define a transport, at call time.

    Read late and by name so that a test can patch ``app.config`` and so that
    an application started with no mail configuration at all still imports.
    """
    return {
        "host": app_config.SMTP_HOST,
        "port": app_config.SMTP_PORT,
        "sender": app_config.SMTP_SENDER,
        "recipient": app_config.SMTP_RECIPIENT,
        "username": app_config.SMTP_USERNAME,
        "password": app_config.SMTP_PASSWORD,
        "tls": app_config.SMTP_TLS,
        "timeout": app_config.SMTP_TIMEOUT_SECONDS,
    }


def missing_settings() -> list[str]:
    """The environment variables that are not set, in configuration order."""
    values = _configured_values()
    return [name for name, key in REQUIRED_SETTINGS if not str(values[key]).strip()]


def smtp_config() -> SMTPConfig | None:
    """The configured transport, or ``None`` when mail is not configured.

    ``None`` is a legitimate state, not an error: the application runs without
    a notifier, and a run that fails says so in its delivery record instead of
    failing twice. Callers that need to *send* ask :func:`require_smtp`.
    """
    if missing_settings():
        return None
    values = _configured_values()
    return SMTPConfig(
        host=values["host"],
        port=values["port"],
        sender=values["sender"],
        recipient=values["recipient"],
        username=values["username"],
        password=values["password"],
        tls=values["tls"],
        timeout=values["timeout"],
    )


def require_smtp() -> SMTPConfig:
    """The configured transport, or a :class:`ConfigError` naming what is missing.

    The message is the deliverable: an unattended system that cannot report a
    failure has to be fixable from the error itself.
    """
    missing = missing_settings()
    if missing:
        raise ConfigError(
            "email notification is not configured: "
            f"{', '.join(missing)} must be set in .env "
            "(see PLAN.md Step 7 and .env.example). "
            "The workflow still records its own failure; only the alert is lost."
        )
    config = smtp_config()
    assert config is not None  # missing_settings() is empty
    return config
