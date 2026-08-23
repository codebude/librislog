"""Tests for app.email module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.email import send_password_reset_email


@pytest.mark.anyio
async def test_send_password_reset_email_success(monkeypatch) -> None:
    """A successful send should call FastMail.send_message with the expected message."""
    monkeypatch.setattr("app.config.settings.password_reset_token_max_age", 3600)
    monkeypatch.setattr("app.config.settings.mail_username", "user")
    monkeypatch.setattr("app.config.settings.mail_password", "pass")
    monkeypatch.setattr("app.config.settings.mail_from", "noreply@example.com")
    monkeypatch.setattr("app.config.settings.mail_server", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.mail_port", 587)

    mock_fastmail_cls = MagicMock()
    mock_fm = MagicMock()
    mock_fm.send_message = AsyncMock()
    mock_fastmail_cls.return_value = mock_fm

    with patch("app.email.FastMail", mock_fastmail_cls):
        await send_password_reset_email("user@example.com", "https://reset.url", locale="en")

    mock_fastmail_cls.assert_called_once()
    mock_fm.send_message.assert_awaited_once()
    message = mock_fm.send_message.call_args[0][0]
    assert len(message.recipients) == 1
    assert message.recipients[0].email == "user@example.com"
    assert "Password Reset" in message.subject
    assert "https://reset.url" in message.body
    assert "60 minutes" in message.body


@pytest.mark.anyio
async def test_send_password_reset_email_exception_logs_error(monkeypatch) -> None:
    """An exception during send should be logged and swallowed."""
    monkeypatch.setattr("app.config.settings.password_reset_token_max_age", 1800)
    monkeypatch.setattr("app.config.settings.mail_username", "user")
    monkeypatch.setattr("app.config.settings.mail_password", "pass")
    monkeypatch.setattr("app.config.settings.mail_from", "noreply@example.com")
    monkeypatch.setattr("app.config.settings.mail_server", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.mail_port", 587)

    mock_fastmail_cls = MagicMock()
    mock_fm = MagicMock()
    mock_fm.send_message = AsyncMock(side_effect=RuntimeError("SMTP failed"))
    mock_fastmail_cls.return_value = mock_fm

    with patch("app.email.logger") as mock_logger:
        with patch("app.email.FastMail", mock_fastmail_cls):
            await send_password_reset_email("user@example.com", "https://reset.url")

    mock_fm.send_message.assert_awaited_once()
    mock_logger.exception.assert_called_once()
    assert "user@example.com" in str(mock_logger.exception.call_args)
