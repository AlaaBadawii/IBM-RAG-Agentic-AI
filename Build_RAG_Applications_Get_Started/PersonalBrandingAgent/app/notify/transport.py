"""The email transport: one interface, one stdlib implementation.

``PLAN.md`` §12.1 decision 3: SMTP, **provider-agnostic at the interface**,
configured for Gmail, stdlib preferred, a fake in tests. That decision is
implemented here as a protocol with exactly one production implementation, so
swapping providers (or dropping in a fake) is a constructor argument rather
than an edit.

    notification service  ->  EmailTransport  ->  SMTPTransport -> smtplib

Everything a transport must be able to answer is on the protocol: what it is
called (``name``, recorded on the delivery row), where it sends (``recipient``),
how it is described without its credentials (``describe``), and how to send
(``send``). Nothing about *what* is being sent is decided here — the message
arrives composed.

The stdlib implementation is deliberately thin, and every failure is
translated into a categorized :class:`~app.notify.errors.NotificationDeliveryError`
rather than escaping as an ``smtplib`` exception: the caller is an unattended
workflow that has to keep going, and the email's failure must not be
indistinguishable from the failure the email was about.
"""
import smtplib
import ssl
from email.message import EmailMessage as MIMEMessage
from typing import Any, Protocol, runtime_checkable

from app.logging_config import get_logger
from app.notify.config import TLS_SSL, TLS_STARTTLS, TRANSPORT_NAME, SMTPConfig
from app.notify.config import smtp_config as configured
from app.notify.enums import NotificationFailureCategory
from app.notify.errors import (
    NotificationConfigurationError,
    NotificationDeliveryError,
)
from app.notify.models import NotificationMessage

logger = get_logger(__name__)


@runtime_checkable
class EmailTransport(Protocol):
    """A way of getting a composed message to a mailbox.

    Implemented by :class:`SMTPTransport` in production and by a capturing fake
    in tests. The protocol is the whole contract, which is what makes
    "provider-agnostic" checkable rather than aspirational.
    """

    #: Recorded on every delivery row so a reader can tell what sent it.
    name: str

    @property
    def recipient(self) -> str:
        """Where this transport sends. Empty when it is not configured."""

    def describe(self) -> str | None:
        """The non-secret configuration, for the delivery record."""

    def send(self, message: NotificationMessage) -> None:
        """Deliver ``message``, or raise a categorized delivery error."""


class SMTPTransport:
    """SMTP over ``smtplib``, configured entirely from configuration.

    Three things this class deliberately does *not* do:

    * **It never guesses an address.** With no configuration there is no
      send: the attempt fails as a configuration failure, which is a fact a
      person can act on, rather than being silently skipped.
    * **It never opens an unbounded socket.** Every connection gets
      ``timeout=``, so an unreachable mail server costs one bounded wait
      instead of holding an unattended run open indefinitely.
    * **It never lets a credential into a message.** ``smtplib`` exception
      text is passed through the shared redaction before it is recorded.
    """

    name = TRANSPORT_NAME

    def __init__(self, config: SMTPConfig | None = None) -> None:
        self._config = config

    @property
    def config(self) -> SMTPConfig | None:
        """The configuration used, resolved from configuration if not given."""
        return self._config if self._config is not None else configured()

    @property
    def recipient(self) -> str:
        config = self.config
        return config.recipient if config is not None else ""

    def describe(self) -> str | None:
        config = self.config
        return config.describe() if config is not None else None

    def send(self, message: NotificationMessage) -> None:
        config = self.config
        if config is None:
            raise NotificationConfigurationError(
                "no email transport is configured: SMTP_HOST, SMTP_SENDER and "
                "SMTP_RECIPIENT must be set before a notification can be sent"
            )
        payload = _payload(config, message)
        try:
            with self._connect(config) as client:
                self._secure(client, config)
                if config.username:
                    client.login(config.username, config.password)
                client.send_message(payload)
        except smtplib.SMTPAuthenticationError as exc:
            raise NotificationDeliveryError(
                NotificationFailureCategory.AUTHENTICATION,
                config.redact(_reason("the mail server rejected the "
                                      "credentials", exc)),
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            # OSError covers sockets, DNS and TLS (socket.timeout, SSLError,
            # ConnectionRefusedError); SMTPException covers the protocol.
            raise NotificationDeliveryError(
                NotificationFailureCategory.TRANSPORT,
                config.redact(_reason("SMTP delivery failed", exc)),
            ) from exc
        logger.info("Notification sent to %s: %s", config.recipient,
                    message.subject)

    def _connect(self, config: SMTPConfig) -> Any:
        context = ssl.create_default_context()
        if config.tls == TLS_SSL:
            return smtplib.SMTP_SSL(config.host, config.port,
                                    timeout=config.timeout, context=context)
        return smtplib.SMTP(config.host, config.port, timeout=config.timeout)

    def _secure(self, client: Any, config: SMTPConfig) -> None:
        if config.tls == TLS_STARTTLS:
            client.starttls(context=ssl.create_default_context())


def _payload(config: SMTPConfig, message: NotificationMessage) -> MIMEMessage:
    """The message as the wire format. Addressing comes from configuration."""
    payload = MIMEMessage()
    payload["From"] = config.sender
    payload["To"] = config.recipient
    payload["Subject"] = message.subject
    payload.set_content(message.body)
    return payload


def _reason(prefix: str, exc: BaseException) -> str:
    """A diagnosable one-line reason, without the credential.

    The exception *type* is always included — ``SMTPAuthenticationError`` and
    ``SMTPServerDisconnected`` are different problems with different remedies
    — and the text is whatever the server said. Both then pass through the
    caller's redaction, because the text comes from outside this process.
    """
    text = str(exc).strip()
    return f"{prefix}: {type(exc).__name__}" + (f": {text}" if text else "")
