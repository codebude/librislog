from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import UserRole


def test_get_profile_returns_current_user(client: TestClient) -> None:
    """The profile endpoint should return the authenticated user."""
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"


def test_get_settings_creates_default_when_missing(client: TestClient, session: Session) -> None:
    """Accessing settings before they exist should create defaults."""
    from app.auth import generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key, encrypt_api_key
    from app.models import User, UserRole, ApiKey

    user = User(firstname="No", lastname="Settings", email="no_settings@example.com",
                role=UserRole.user, hashed_password=get_password_hash("secret"))
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    key_plain = generate_api_key()
    session.add(ApiKey(user_id=user.id, key_prefix=get_api_key_prefix(key_plain),
                       key_hash=hash_api_key(key_plain), key_encrypted=encrypt_api_key(key_plain),
                       description="Test"))
    session.commit()

    client.headers["X-API-Key"] = key_plain
    resp = client.get("/api/profile/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "en"
    assert data["user_id"] == user.id


def test_update_settings_creates_default_when_missing(client: TestClient, session: Session) -> None:
    """Updating settings before they exist should create defaults and apply the update."""
    from app.auth import generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key, encrypt_api_key
    from app.models import User, UserRole, ApiKey

    user = User(firstname="No", lastname="Settings2", email="no_settings2@example.com",
                role=UserRole.user, hashed_password=get_password_hash("secret"))
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    key_plain = generate_api_key()
    session.add(ApiKey(user_id=user.id, key_prefix=get_api_key_prefix(key_plain),
                       key_hash=hash_api_key(key_plain), key_encrypted=encrypt_api_key(key_plain),
                       description="Test"))
    session.commit()

    client.headers["X-API-Key"] = key_plain
    resp = client.patch("/api/profile/settings", json={"language": "de"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "de"
    assert data["user_id"] == user.id


def test_reset_data_rolls_back_on_exception(client: TestClient, monkeypatch) -> None:
    """An exception during data reset should be propagated."""
    import app.routers.profile as profile_module

    def fake_delete(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(profile_module, "delete_user_reading_data", fake_delete)

    with pytest.raises(RuntimeError, match="boom"):
        client.post("/api/profile/reset-data", json={"confirmation": "DELETE ALL MY DATA"})


def test_delete_account_rolls_back_on_exception(
    client: TestClient, create_user_with_key: Callable[..., Any], monkeypatch,
) -> None:
    """An exception during account deletion should be propagated."""
    import app.routers.profile as profile_module

    user, key = create_user_with_key(email="delete_me@example.com", role=UserRole.user)
    client.headers["X-API-Key"] = key

    def fake_delete(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(profile_module, "delete_user_account_data", fake_delete)

    with pytest.raises(RuntimeError, match="boom"):
        client.request("DELETE", "/api/profile/account", json={"confirmation": "DELETE MY ACCOUNT"})


def test_delete_api_key_not_found(client: TestClient) -> None:
    """Deleting a non-existent API key should return 404."""
    resp = client.delete("/api/profile/api-keys/99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "API key not found"
