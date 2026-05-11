from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import get_session
from app.main import app
from app.models import ApiKey, User, UserRole, UserSettings


def test_auth_me_returns_current_user(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "admin"


def test_auth_me_rejects_invalid_api_key(client: TestClient):
    resp = client.get("/api/auth/me", headers={"X-API-Key": "lk_invalid"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


def test_auth_login_returns_user_and_api_key(client: TestClient):
    login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["email"] == "test@example.com"
    assert payload["api_key"].startswith("lk_")

    me = client.get("/api/auth/me", headers={"X-API-Key": payload["api_key"]})
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"


def test_auth_login_rejects_wrong_password(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_auth_setup_forbidden_when_admin_exists(client: TestClient):
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


def test_auth_setup_flow_when_no_admin(session: Session):
    def override_get_session():
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
            assert body["api_key"].startswith("lk_")

            after = raw_client.get("/api/auth/setup-required")
            assert after.status_code == 200
            assert after.json() == {"required": False}

            me = raw_client.get("/api/auth/me", headers={"X-API-Key": body["api_key"]})
            assert me.status_code == 200
            assert me.json()["email"] == "first-admin@example.com"
    finally:
        app.dependency_overrides.clear()


def test_profile_patch_updates_fields(client: TestClient):
    resp = client.patch(
        "/api/profile",
        json={"firstname": "Updated", "lastname": "Name", "password": "Newpass1!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["firstname"] == "Updated"
    assert data["lastname"] == "Name"


def test_profile_patch_ignores_email_changes(client: TestClient, create_user_with_key):
    create_user_with_key(email="other@example.com")
    resp = client.patch("/api/profile", json={"email": "other@example.com"})
    assert resp.status_code == 422


def test_profile_patch_changes_password_and_login_uses_new_password(client: TestClient):
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


def test_profile_patch_rejects_weak_password(client: TestClient):
    resp = client.patch("/api/profile", json={"password": "weak"})
    assert resp.status_code == 400


def test_profile_settings_get_and_update(client: TestClient):
    current = client.get("/api/profile/settings")
    assert current.status_code == 200
    assert current.json()["language"] == "en"

    updated = client.patch("/api/profile/settings", json={"language": "de"})
    assert updated.status_code == 200
    assert updated.json()["language"] == "de"


def test_profile_api_key_lifecycle(client: TestClient):
    listed = client.get("/api/profile/api-keys")
    assert listed.status_code == 200
    initial = listed.json()
    assert any(k["is_primary"] for k in initial)

    created = client.post("/api/profile/api-keys", json={"description": "CLI key"})
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["key"].startswith("lk_")
    assert created_data["api_key"]["description"] == "CLI key"
    assert created_data["api_key"]["is_primary"] is False

    delete_resp = client.delete(f"/api/profile/api-keys/{created_data['api_key']['id']}")
    assert delete_resp.status_code == 204


def test_profile_cannot_delete_primary_api_key(client: TestClient):
    listed = client.get("/api/profile/api-keys")
    assert listed.status_code == 200
    primary = next(k for k in listed.json() if k["is_primary"])

    resp = client.delete(f"/api/profile/api-keys/{primary['id']}")
    assert resp.status_code == 403


def test_users_list_requires_admin(client: TestClient, create_user_with_key):
    _user, user_key = create_user_with_key(email="member@example.com", role=UserRole.user)
    resp = client.get("/api/users", headers={"X-API-Key": user_key})
    assert resp.status_code == 403


def test_users_create_creates_user_settings_and_primary_key(client: TestClient, session: Session):
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
    assert body["api_key"].startswith("lk_")

    user = session.exec(select(User).where(User.email == "new-user@example.com")).first()
    assert user is not None

    settings = session.exec(select(UserSettings).where(UserSettings.user_id == user.id)).first()
    assert settings is not None
    assert settings.language == "en"

    primary_key = session.exec(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.is_primary.is_(True), ApiKey.revoked_at.is_(None))
    ).first()
    assert primary_key is not None
    assert primary_key.key_encrypted is not None


def test_users_create_rejects_duplicate_email(client: TestClient):
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


def test_users_create_rejects_weak_password(client: TestClient):
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


def test_users_update_user_allows_admin_email_change(client: TestClient, create_user_with_key):
    user, _key = create_user_with_key(email="member-update@example.com", role=UserRole.user)
    resp = client.patch(
        f"/api/users/{user.id}",
        json={"email": "member-updated@example.com", "firstname": "Renamed"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "member-updated@example.com"
    assert data["firstname"] == "Renamed"


def test_users_update_user_rejects_duplicate_email(client: TestClient, create_user_with_key):
    user_a, _ = create_user_with_key(email="dup-a@example.com", role=UserRole.user)
    create_user_with_key(email="dup-b@example.com", role=UserRole.user)
    resp = client.patch(f"/api/users/{user_a.id}", json={"email": "dup-b@example.com"})
    assert resp.status_code == 400


def test_users_update_user_rejects_weak_password(client: TestClient, create_user_with_key):
    user, _ = create_user_with_key(email="weak-update@example.com", role=UserRole.user)
    resp = client.patch(f"/api/users/{user.id}", json={"password": "weak"})
    assert resp.status_code == 400


def test_users_update_user_rejects_self_role_demotion(client: TestClient):
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    me_id = me.json()["id"]

    resp = client.patch(f"/api/users/{me_id}", json={"role": "user"})
    assert resp.status_code == 403


def test_users_delete_rejects_self_delete(client: TestClient):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    me_id = resp.json()["id"]

    deleted = client.delete(f"/api/users/{me_id}")
    assert deleted.status_code == 403


def test_users_delete_soft_revokes_keys_and_removes_user(
    client: TestClient,
    create_user_with_key,
    session: Session,
):
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
