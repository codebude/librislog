from collections.abc import Callable, Generator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import (
    decrypt_api_key,
    encrypt_api_key,
    get_password_hash,
    hash_api_key,
    require_user_by_api_key,
)
from app.database import get_session
from app.main import app
from app.models import ApiKey, Book, OidcLink, ReadingProgress, Tag, User, UserRole, UserSettings


def test_auth_me_returns_current_user(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "admin"


def test_auth_me_rejects_invalid_api_key(client: TestClient) -> None:
    resp = client.get("/api/auth/me", headers={"X-API-Key": "lk_invalid"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


def test_auth_me_rejects_without_cookie_or_api_key(client: TestClient) -> None:
    client.post("/api/auth/logout")
    client.headers.pop("X-API-Key", None)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_auth_login_returns_user_and_api_key(client: TestClient) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["email"] == "test@example.com"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"


def test_auth_logout_clears_cookie_session(client: TestClient) -> None:
    before = client.get("/api/auth/me")
    assert before.status_code == 200

    out = client.post("/api/auth/logout")
    assert out.status_code == 200

    client.headers.pop("X-API-Key", None)
    after = client.get("/api/auth/me")
    assert after.status_code == 401


def test_auth_login_rejects_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_auth_setup_forbidden_when_admin_exists(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/setup",
        json={
            "firstname": "A",
            "lastname": "B",
            "email": "new-admin@example.com",
            "password": "Secret123!",
        },
    )
    assert resp.status_code == 403


def test_auth_setup_flow_when_no_admin(session: Session) -> None:
    def override_get_session() -> Generator[Session, None, None]:
        """Override the database session dependency to use the test session."""
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as raw_client:
            before = raw_client.get("/api/auth/setup-required")
            assert before.status_code == 200
            assert before.json() == {"required": True}

            setup = raw_client.post(
                "/api/auth/setup",
                json={
                    "firstname": "First",
                    "lastname": "Admin",
                    "email": "first-admin@example.com",
                    "password": "Secret123!",
                },
            )
            assert setup.status_code == 200
            body = setup.json()
            assert body["user"]["role"] == "admin"

            after = raw_client.get("/api/auth/setup-required")
            assert after.status_code == 200
            assert after.json() == {"required": False}

            me = raw_client.get("/api/auth/me")
            assert me.status_code == 200
            assert me.json()["email"] == "first-admin@example.com"
    finally:
        app.dependency_overrides.clear()


def test_auth_login_allows_access_without_api_key_header(client: TestClient) -> None:
    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert login.status_code == 200

    client.headers.pop("X-API-Key", None)
    me = client.get("/api/auth/me")
    assert me.status_code == 200


def test_cookie_auth_rejects_mutation_without_csrf_token(client: TestClient) -> None:
    client.post("/api/auth/logout")
    client.headers.pop("X-API-Key", None)

    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert login.status_code == 200

    resp = client.patch("/api/profile", json={"firstname": "NoCsrf"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Invalid CSRF token"


def test_cookie_auth_allows_mutation_with_csrf_token(client: TestClient) -> None:
    client.post("/api/auth/logout")
    client.headers.pop("X-API-Key", None)

    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert login.status_code == 200

    csrf = client.get("/api/auth/csrf")
    assert csrf.status_code == 200
    token = csrf.json()["csrf_token"]

    resp = client.patch(
        "/api/profile",
        json={"firstname": "WithCsrf"},
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["firstname"] == "WithCsrf"


def test_profile_patch_updates_fields(client: TestClient) -> None:
    resp = client.patch(
        "/api/profile",
        json={"firstname": "Updated", "lastname": "Name", "password": "Newpass1!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["firstname"] == "Updated"
    assert data["lastname"] == "Name"


def test_profile_patch_ignores_email_changes(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    create_user_with_key(email="other@example.com")
    resp = client.patch("/api/profile", json={"email": "other@example.com"})
    assert resp.status_code == 422


def test_profile_patch_changes_password_and_login_uses_new_password(client: TestClient) -> None:
    updated = client.patch("/api/profile", json={"password": "Changed1!"})
    assert updated.status_code == 200

    old_login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "Changed1!"},
    )
    assert new_login.status_code == 200


def test_profile_patch_rejects_weak_password(client: TestClient) -> None:
    resp = client.patch("/api/profile", json={"password": "weak"})
    assert resp.status_code == 400


def test_profile_settings_get_and_update(client: TestClient) -> None:
    current = client.get("/api/profile/settings")
    assert current.status_code == 200
    assert current.json()["language"] == "en"
    assert current.json()["timezone"] == "UTC"
    assert current.json()["theme"] == "light"
    assert current.json()["custom_theme"] is None

    updated = client.patch("/api/profile/settings", json={"language": "de"})
    assert updated.status_code == 200
    assert updated.json()["language"] == "de"
    assert updated.json()["timezone"] == "UTC"

    tz_updated = client.patch("/api/profile/settings", json={"timezone": "Europe/Berlin"})
    assert tz_updated.status_code == 200
    assert tz_updated.json()["timezone"] == "Europe/Berlin"

    theme_updated = client.patch("/api/profile/settings", json={"theme": "dark"})
    assert theme_updated.status_code == 200
    assert theme_updated.json()["theme"] == "dark"
    assert theme_updated.json()["custom_theme"] is None

    custom_updated = client.patch("/api/profile/settings", json={"theme": "custom", "custom_theme": "dracula"})
    assert custom_updated.status_code == 200
    assert custom_updated.json()["theme"] == "custom"
    assert custom_updated.json()["custom_theme"] == "dracula"


def test_profile_api_key_lifecycle(client: TestClient) -> None:
    listed = client.get("/api/profile/api-keys")
    assert listed.status_code == 200

    created = client.post("/api/profile/api-keys", json={"description": "CLI key"})
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["key"].startswith("lk_")
    assert created_data["api_key"]["description"] == "CLI key"

    delete_resp = client.delete(f"/api/profile/api-keys/{created_data['api_key']['id']}")
    assert delete_resp.status_code == 204

def test_users_list_requires_admin(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    _user, user_key = create_user_with_key(email="member@example.com", role=UserRole.user)
    resp = client.get("/api/users", headers={"X-API-Key": user_key})
    assert resp.status_code == 403


def test_users_create_creates_user_settings(client: TestClient, session: Session) -> None:
    resp = client.post(
        "/api/users",
        json={
            "firstname": "New",
            "lastname": "User",
            "email": "new-user@example.com",
            "password": "Secret123!",
            "role": "user",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "new-user@example.com"

    user = session.exec(select(User).where(User.email == "new-user@example.com")).first()
    assert user is not None

    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user.id)).first()
    assert settings is not None
    assert settings.language == "en"
    assert settings.timezone == "UTC"
    assert settings.theme == "light"
    assert settings.custom_theme is None

def test_users_create_rejects_duplicate_email(client: TestClient) -> None:
    resp = client.post(
        "/api/users",
        json={
            "firstname": "Dup",
            "lastname": "User",
            "email": "test@example.com",
            "password": "Secret123!",
            "role": "user",
        },
    )
    assert resp.status_code == 400


def test_users_create_rejects_weak_password(client: TestClient) -> None:
    resp = client.post(
        "/api/users",
        json={
            "firstname": "Weak",
            "lastname": "Pass",
            "email": "weak-pass@example.com",
            "password": "weakpass",
            "role": "user",
        },
    )
    assert resp.status_code == 400


def test_users_update_user_allows_admin_email_change(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    user, _key = create_user_with_key(email="member-update@example.com", role=UserRole.user)
    resp = client.patch(
        f"/api/users/{user.id}",
        json={"email": "member-updated@example.com", "firstname": "Renamed"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "member-updated@example.com"
    assert data["firstname"] == "Renamed"


def test_users_update_user_rejects_duplicate_email(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    user_a, _ = create_user_with_key(email="dup-a@example.com", role=UserRole.user)
    create_user_with_key(email="dup-b@example.com", role=UserRole.user)
    resp = client.patch(f"/api/users/{user_a.id}", json={"email": "dup-b@example.com"})
    assert resp.status_code == 400


def test_users_update_user_rejects_weak_password(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    user, _ = create_user_with_key(email="weak-update@example.com", role=UserRole.user)
    resp = client.patch(f"/api/users/{user.id}", json={"password": "weak"})
    assert resp.status_code == 400


def test_users_update_user_password_success(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
) -> None:
    """Admin updating another user's password with a valid password should succeed."""
    user, _ = create_user_with_key(email="pw-update@example.com", role=UserRole.user)
    resp = client.patch(
        f"/api/users/{user.id}",
        json={"password": "NewSecret1!"},
    )
    assert resp.status_code == 200


def test_users_update_user_rejects_self_role_demotion(client: TestClient) -> None:
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    me_id = me.json()["id"]

    resp = client.patch(f"/api/users/{me_id}", json={"role": "user"})
    assert resp.status_code == 403


def test_users_delete_rejects_self_delete(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    me_id = resp.json()["id"]

    deleted = client.delete(f"/api/users/{me_id}")
    assert deleted.status_code == 403


def test_users_delete_soft_revokes_keys_and_removes_user(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
    session: Session,
) -> None:
    user, _key = create_user_with_key(email="delete-me@example.com", role=UserRole.user)
    user_id = user.id

    resp = client.delete(f"/api/users/{user_id}")
    assert resp.status_code == 204

    deleted_user = session.get(User, user_id)
    assert deleted_user is None

    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).first()
    assert settings is None

    keys = session.exec(select(ApiKey).where(ApiKey.user_id == user_id)).all()
    assert keys
    assert all(k.revoked_at is not None for k in keys)


def test_auth_decrypt_api_key_roundtrip() -> None:
    """encrypt then decrypt should return the original value."""
    original = "my-secret-api-key"
    encrypted = encrypt_api_key(original)
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original


def test_auth_require_user_by_api_key_missing_header(session: Session) -> None:
    """Missing API key header should raise 401."""
    with pytest.raises(HTTPException) as exc_info:
        require_user_by_api_key(x_api_key=None, session=session)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing API key"


def test_auth_require_user_by_api_key_invalid_user(session: Session) -> None:
    """API key exists but user was deleted — should raise 401."""
    key_plain = "lk_testkey123"
    key = ApiKey(
        user_id=99999,
        key_prefix=key_plain[:12],
        key_hash=hash_api_key(key_plain),
        key_encrypted="encrypted",
        description="test",
    )
    session.add(key)
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        require_user_by_api_key(x_api_key=key_plain, session=session)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid API key user"


def test_setup_email_already_registered_no_admin(session: Session) -> None:
    """Setup with an existing user's email should return 400."""
    user = User(
        firstname="Existing",
        lastname="User",
        email="existing@example.com",
        role=UserRole.user,
        hashed_password=get_password_hash("password"),
    )
    session.add(user)
    session.commit()

    def override_get_session() -> Generator[Session, None, None]:
        """Override the database session dependency to use the test session."""
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as raw_client:
            resp = raw_client.post(
                "/api/auth/setup",
                json={
                    "firstname": "New",
                    "lastname": "Admin",
                    "email": "existing@example.com",
                    "password": "Secret123!",
                },
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Email already registered"
    finally:
        app.dependency_overrides.clear()


def test_csrf_token_not_authenticated(client: TestClient) -> None:
    """CSRF endpoint without session should return 401."""
    client.post("/api/auth/logout")
    client.headers.pop("X-API-Key", None)
    resp = client.get("/api/auth/csrf")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_users_list_returns_users(client: TestClient) -> None:
    """Admin listing users should return the user list."""
    resp = client.get("/api/users")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["email"] == "test@example.com"


def test_users_update_user_not_found(client: TestClient) -> None:
    """Updating a non-existent user should return 404."""
    resp = client.patch("/api/users/99999", json={"firstname": "Ghost"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_users_delete_user_not_found(client: TestClient) -> None:
    """Deleting a non-existent user should return 404."""
    resp = client.delete("/api/users/99999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_oidc_config_disabled_by_default(client: TestClient) -> None:
    resp = client.get("/api/oidc/config")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_oidc_link_status_disabled_by_default(client: TestClient) -> None:
    resp = client.get("/api/oidc/link-status")
    assert resp.status_code == 200
    assert resp.json()["linked"] is False


def test_profile_reset_data_requires_confirmation_phrase(client: TestClient) -> None:
    resp = client.post("/api/profile/reset-data", json={"confirmation": "WRONG"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Confirmation phrase does not match."


def test_profile_reset_data_deletes_books_tags_progress(client: TestClient) -> None:
    b1 = client.post("/api/books", json={"title": "A", "author": "Test Author", "page_count": 100, "tags": "one,two"}).json()
    b2 = client.post("/api/books", json={"title": "B", "author": "Test Author", "page_count": 100, "tags": "one"}).json()
    client.post(f"/api/books/{b1['id']}/progress", json={"page": 10})
    client.post(f"/api/books/{b1['id']}/progress", json={"page": 20})

    resp = client.post("/api/profile/reset-data", json={"confirmation": "DELETE ALL MY DATA"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"]["books"] == 2
    assert data["deleted"]["tags"] == 2
    assert data["deleted"]["progress_entries"] == 2

    assert client.get("/api/books").json() == []


def test_profile_delete_account_rejects_last_admin(client: TestClient) -> None:
    resp = client.request("DELETE", "/api/profile/account", json={"confirmation": "DELETE MY ACCOUNT"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Cannot delete the last administrator account."


def test_profile_delete_account_deletes_regular_user_data(
    client: TestClient,
    create_user_with_key: Callable[..., tuple[User, str]],
    session: Session,
) -> None:
    user, key = create_user_with_key(email="danger@example.com", role=UserRole.user)
    with TestClient(client.app) as c2:
        c2.headers.update({"X-API-Key": key})

        create = c2.post("/api/books", json={"title": "To Delete", "author": "Test Author", "page_count": 100, "tags": "x"})
        assert create.status_code == 201
        book_id = create.json()["id"]
        c2.post(f"/api/books/{book_id}/progress", json={"page": 7})

        session.add(OidcLink(user_id=user.id, provider_id="google", oidc_sub="sub-123"))
        session.commit()

        resp = c2.request("DELETE", "/api/profile/account", json={"confirmation": "DELETE MY ACCOUNT"})
        assert resp.status_code == 204

    assert session.get(User, user.id) is None
    assert session.exec(select(UserSettings).where(UserSettings.user_id == user.id)).first() is None
    assert session.exec(select(Book).where(Book.user_id == user.id)).first() is None
    assert session.exec(select(ReadingProgress).where(ReadingProgress.user_id == user.id)).first() is None
    assert session.exec(select(Tag).where(Tag.user_id == user.id)).first() is None
    assert session.exec(select(OidcLink).where(OidcLink.user_id == user.id)).first() is None

    keys = session.exec(select(ApiKey).where(ApiKey.user_id == user.id)).all()
    assert keys
    assert all(k.revoked_at is not None for k in keys)
