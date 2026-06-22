"""Email sending utilities using fastapi-mail."""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.config import settings
from app.i18n import translate

logger = logging.getLogger(__name__)


def _connection_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=settings.mail_starttls,
        MAIL_SSL_TLS=settings.mail_ssl_tls,
        USE_CREDENTIALS=bool(settings.mail_username) and bool(settings.mail_password),
        VALIDATE_CERTS=True,
    )


async def send_password_reset_email(recipient: str, reset_url: str, locale: str = "en") -> None:
    conf = _connection_config()
    duration_minutes = settings.password_reset_token_max_age // 60
    message = MessageSchema(
        subject=translate("email.passwordResetSubject", locale=locale),
        recipients=[recipient],
        body=translate(
            "email.passwordResetBody",
            locale=locale,
            duration_minutes=str(duration_minutes),
            reset_url=reset_url,
        ),
        subtype=MessageType.html,
    )
    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception:
        logger.exception("Failed to send password reset email to %s", recipient)
