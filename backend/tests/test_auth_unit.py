"""Unit tests for app.auth password reset tokens and session credential checks."""

import pytest
from fastapi import HTTPException, Request
from sqlmodel import Session

from app.auth import (
    generate_password_reset_token,
    require_user,
    verify_password_reset_token,
)
from app.models import User, UserRole


def test_password_reset_token_round_trip() -> None:
    """A freshly generated token should verify and return the payload."""
    token = generate_password_reset_token("user@example.com", credentials_version=3)
    payload = verify_password_reset_token(token)
    assert payload == {"email": "user@example.com", "credentials_version": 3}


def test_password_reset_token_expired() -> None:
    """A token verified with max_age=-1 should be rejected as expired."""
    token = generate_password_reset_token("user@example.com")
    assert verify_password_reset_token(token, max_age=-1) is None


def test_password_reset_token_tampered() -> None:
    """A tampered token should fail verification."""
    token = generate_password_reset_token("user@example.com")
    assert verify_password_reset_token(token + "x") is None


def test_password_reset_token_wrong_shape(monkeypatch) -> None:
    """A token whose payload lacks required keys should be rejected."""
    from app.auth import _password_reset_serializer

    # Manually sign a payload with the wrong shape.
    token = _password_reset_serializer.dumps("just-a-string")
    assert verify_password_reset_token(token) is None


def test_require_user_session_credentials_version_mismatch(session: Session) -> None:
    """A session whose credentials_version does not match the user should be cleared and rejected."""
    user = User(
        firstname="A",
        lastname="B",
        email="session@example.com",
        role=UserRole.user,
        hashed_password="hashed",
        credentials_version=2,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "session": {
            "user_id": user.id,
            "credentials_version": 1,
            "csrf_token": "csrf",
        },
    }
    request = Request(scope)

    with pytest.raises(HTTPException) as exc_info:
        require_user(request=request, x_api_key=None, x_csrf_token=None, session=session)

    assert exc_info.value.status_code == 401
    assert "session expired" in exc_info.value.detail.lower()
    assert request.session == {}
