from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlmodel import Session, select
from unittest.mock import patch

from app.config import settings
from app.models import AvatarSource, OidcLink, User, UserImage
from app.services.avatar_storage import StoredAvatar


class FakeOidcClient:
    _token: dict[str, Any]
    _redirect_target: str
    last_redirect_uri: str | None

    def __init__(
        self,
        *,
        token: dict[str, Any] | None = None,
        redirect_target: str = "https://issuer.example/auth",
    ) -> None:
        self._token = token or {}
        self._redirect_target = redirect_target
        self.last_redirect_uri = None

    async def authorize_access_token(self, _request: Any) -> dict[str, Any]:
        return self._token

    async def authorize_redirect(self, _request: Any, redirect_uri: str) -> RedirectResponse:
        self.last_redirect_uri = redirect_uri
        return RedirectResponse(url=self._redirect_target, status_code=302)


class FakeOidcClientRedirectError(FakeOidcClient):
    async def authorize_redirect(self, _request: Any, redirect_uri: str) -> RedirectResponse:
        raise RuntimeError("redirect error")


class FakeOidcClientTokenError(FakeOidcClient):
    async def authorize_access_token(self, _request: Any) -> dict[str, Any]:
        raise RuntimeError("token error")


def _set_oidc_enabled(monkeypatch: MonkeyPatch) -> None:
    """Enable OIDC via monkeypatching for tests that require OIDC to be active."""
    monkeypatch.setattr("app.routers.oidc.oidc_is_enabled", lambda: True)
    monkeypatch.setattr(settings, "oidc_provider_id", "test-oidc")
    monkeypatch.setattr(settings, "oidc_provider_name", "Test SSO")


# ── Tests for app.oidc.get_oidc_client (lines 23-36) ───────────────────────────


def test_get_oidc_client_returns_none_when_disabled(monkeypatch: MonkeyPatch) -> None:
    """Lines 23-24: when OIDC is disabled, get_oidc_client returns None."""
    from app.oidc import get_oidc_client

    monkeypatch.setattr("app.oidc.oidc_is_enabled", lambda: False)
    assert get_oidc_client() is None


def test_get_oidc_client_registers_and_returns_client_when_enabled(monkeypatch: MonkeyPatch) -> None:
    """Lines 26-36: when enabled and not yet registered, oauth.register is called."""
    from app.oidc import get_oidc_client

    monkeypatch.setattr("app.oidc.oidc_is_enabled", lambda: True)
    monkeypatch.setattr(settings, "oidc_provider_id", "test-oidc")
    monkeypatch.setattr(settings, "oidc_client_id", "client-id")
    monkeypatch.setattr(settings, "oidc_client_secret", "client-secret")
    monkeypatch.setattr(settings, "oidc_well_known_url", "https://issuer.example/.well-known/openid-configuration")
    monkeypatch.setattr(settings, "oidc_scope", "openid email profile")
    monkeypatch.setattr("app.oidc._registered", False, raising=False)

    fake_client = FakeOidcClient()
    with patch("app.oidc.oauth.register") as mock_register:
        with patch("app.oidc.oauth.create_client", return_value=fake_client) as mock_create:
            result = get_oidc_client()

    assert result is fake_client
    mock_register.assert_called_once()
    mock_create.assert_called_once_with("test-oidc")


def test_get_oidc_client_reuses_existing_registration(monkeypatch: MonkeyPatch) -> None:
    """Lines 26-34 skipped: when already registered, oauth.register is not called again."""
    from app.oidc import get_oidc_client

    monkeypatch.setattr("app.oidc.oidc_is_enabled", lambda: True)
    monkeypatch.setattr(settings, "oidc_provider_id", "test-oidc")
    monkeypatch.setattr("app.oidc._registered", True, raising=False)

    fake_client = FakeOidcClient()
    with patch("app.oidc.oauth.register") as mock_register:
        with patch("app.oidc.oauth.create_client", return_value=fake_client) as mock_create:
            result = get_oidc_client()

    assert result is fake_client
    mock_register.assert_not_called()
    mock_create.assert_called_once_with("test-oidc")


def test_oidc_config_enabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)

    response = client.get("/api/oidc/config")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider_id"] == "test-oidc"
    assert data["provider_name"] == "Test SSO"
    assert data["auto_redirect"] is False


def test_oidc_config_auto_redirect_when_password_login_disabled(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    """Auto-redirect is exposed only when password login is unavailable."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr(settings, "oidc_auto_redirect", True)
    monkeypatch.setattr(settings, "password_login_enabled", False)

    data = client.get("/api/oidc/config").json()

    assert data["auto_redirect"] is True


def test_oidc_config_auto_redirect_ignored_when_password_login_enabled(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    """The backend refuses auto-redirect while password login is available."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr(settings, "oidc_auto_redirect", True)
    monkeypatch.setattr(settings, "password_login_enabled", True)

    data = client.get("/api/oidc/config").json()

    assert data["auto_redirect"] is False


def test_oidc_login_returns_404_when_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: None)

    response = client.get("/api/oidc/login")

    assert response.status_code == 404
    assert response.json()["detail"] == "OIDC is not enabled"


def test_oidc_callback_unlinked_redirects_to_login_warning(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"sub": "sub-unlinked"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "not+linked" in response.headers["location"]


def test_oidc_callback_linked_redirects_with_cookie_session(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"sub": "sub-linked"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-linked",
            oidc_email="linked@example.com",
            oidc_name="Linked User",
        )
    )
    session.commit()

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)

    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    assert parsed.path == "/auth/oidc/callback"
    assert parsed.query == ""


def test_oidc_link_status_reports_unlinked(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)

    response = client.get("/api/oidc/link-status")

    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is False
    assert data["provider_name"] == "Test SSO"


def test_oidc_link_status_reports_linked(client: TestClient, session: Session, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-status",
            oidc_email="status@example.com",
            oidc_name="Status User",
        )
    )
    session.commit()

    response = client.get("/api/oidc/link-status")

    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is True
    assert data["provider_name"] == "Test SSO"
    assert data["oidc_email"] == "status@example.com"


def test_oidc_link_start_returns_authorize_redirect_url(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)

    response = client.post("/api/oidc/link")

    assert response.status_code == 200
    assert response.json()["redirect_url"] == "/api/oidc/link/authorize"


def test_oidc_link_authorize_requires_link_session(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/link/authorize", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")


def test_oidc_link_authorize_redirects_to_provider_after_start(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(redirect_target="https://issuer.example/authorize")
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    authorize = client.get("/api/oidc/link/authorize", follow_redirects=False)

    assert authorize.status_code == 302
    assert authorize.headers["location"] == "https://issuer.example/authorize"


def test_oidc_link_callback_creates_link(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "sub-create-link",
                "email": "new-link@example.com",
                "name": "New Link",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    callback = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/auth/oidc/link-callback?status=success"

    link = session.exec(select(OidcLink).where(OidcLink.user_id == user_id)).first()
    assert link is not None
    assert link.oidc_sub == "sub-create-link"


def test_oidc_link_callback_rejects_sub_already_linked_to_another_user(
    client: TestClient,
    session: Session,
    create_user_with_key: Callable[..., tuple[User, str]],
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)

    other_user, _ = create_user_with_key(email="other-oidc@example.com")
    assert other_user.id is not None
    session.add(
        OidcLink(
            user_id=other_user.id,
            provider_id="test-oidc",
            oidc_sub="shared-sub",
            oidc_email="other-oidc@example.com",
            oidc_name="Other OIDC",
        )
    )
    session.commit()

    fake = FakeOidcClient(token={"userinfo": {"sub": "shared-sub", "email": "shared@example.com"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    callback = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "already+linked+to+another+user" in callback.headers["location"]


def test_oidc_unlink_removes_existing_link(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-unlink",
            oidc_email="unlink@example.com",
            oidc_name="Unlink User",
        )
    )
    session.commit()

    response = client.delete("/api/oidc/unlink")
    assert response.status_code == 204

    link = session.exec(select(OidcLink).where(OidcLink.user_id == user_id)).first()
    assert link is None


def test_oidc_config_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.oidc_is_enabled", lambda: False)
    response = client.get("/api/oidc/config")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["provider_id"] is None
    assert data["provider_name"] is None
    assert data["auto_redirect"] is False


def test_oidc_login_with_x_forwarded_proto(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get(
        "/api/oidc/login",
        headers={"X-Forwarded-Proto": "https", "Host": "proxy.example"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert fake.last_redirect_uri == "https://proxy.example/api/oidc/callback"


def test_oidc_login_uses_configured_callback_base_url(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """A configured callback base replaces the host the backend sees."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr(settings, "oidc_callback_base_url", "http://dev.example.lan:5173/")
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get(
        "/api/oidc/login",
        headers={"Host": "localhost:8000"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert fake.last_redirect_uri == "http://dev.example.lan:5173/api/oidc/callback"


def test_oidc_login_ignores_invalid_callback_base_url(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """A value without scheme and host falls back to the request host."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr(settings, "oidc_callback_base_url", "dev.example.lan:5173")
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/login", follow_redirects=False)

    assert response.status_code == 302
    assert fake.last_redirect_uri == "http://testserver/api/oidc/callback"


def test_oidc_link_authorize_uses_configured_callback_base_url(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """Account linking uses the same configured callback base as login."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr(settings, "oidc_callback_base_url", "https://books.example.com")
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    authorize = client.get("/api/oidc/link/authorize", follow_redirects=False)

    assert authorize.status_code == 302
    assert fake.last_redirect_uri == "https://books.example.com/api/oidc/link-callback"


def test_oidc_login_authorize_redirect_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClientRedirectError()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "unavailable" in response.headers["location"]


def test_oidc_callback_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: None)
    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "not+enabled" in response.headers["location"]


def test_oidc_callback_authorize_access_token_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClientTokenError()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "failed" in response.headers["location"]


def test_oidc_callback_missing_sub(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"email": "a@b.com"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "missing+subject" in response.headers["location"]


def test_oidc_callback_linked_user_missing(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"sub": "orphan-sub"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    session.add(
        OidcLink(
            user_id=99999,
            provider_id="test-oidc",
            oidc_sub="orphan-sub",
            oidc_email="orphan@example.com",
            oidc_name="Orphan",
        )
    )
    session.commit()

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "no+longer+exists" in response.headers["location"]


def test_oidc_link_status_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.oidc_is_enabled", lambda: False)
    response = client.get("/api/oidc/link-status")
    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is False
    assert data["provider_name"] is None
    assert data["oidc_email"] is None
    assert data["oidc_name"] is None


def test_oidc_link_start_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.oidc_is_enabled", lambda: False)
    response = client.post("/api/oidc/link")
    assert response.status_code == 404
    assert response.json()["detail"] == "OIDC is not enabled"


def test_oidc_link_authorize_client_none(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: None)
    response = client.get("/api/oidc/link/authorize")
    assert response.status_code == 404
    assert response.json()["detail"] == "OIDC is not enabled"


def test_oidc_link_authorize_redirect_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClientRedirectError()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    response = client.get("/api/oidc/link/authorize", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "unavailable" in response.headers["location"]


def test_oidc_link_callback_disabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: None)
    response = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "not+enabled" in response.headers["location"]


def test_oidc_link_callback_missing_session(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "Missing+link+session" in response.headers["location"]


def test_oidc_link_callback_authorize_access_token_exception(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClientTokenError()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    response = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "linking+failed" in response.headers["location"]


def test_oidc_link_callback_missing_sub(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"email": "a@b.com"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    response = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")
    assert "missing+subject" in response.headers["location"]


def test_oidc_link_callback_updates_existing_link(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    _set_oidc_enabled(monkeypatch)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]

    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="old-sub",
            oidc_email="old@example.com",
            oidc_name="Old Name",
        )
    )
    session.commit()

    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "new-sub",
                "email": "new@example.com",
                "name": "New Name",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    response = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/oidc/link-callback?status=success"

    link = session.exec(select(OidcLink).where(OidcLink.user_id == user_id)).first()
    assert link is not None
    assert link.oidc_sub == "new-sub"
    assert link.oidc_email == "new@example.com"
    assert link.oidc_name == "New Name"


def _request_with_host(host: str):
    """Build a minimal request so redirect bases can be tested directly."""
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"host", host.encode())],
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def test_frontend_base_url_ignores_loopback_for_remote_host(monkeypatch: MonkeyPatch) -> None:
    """An old localhost PUBLIC_APP_URL must not redirect production users."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "http://localhost:5173")

    request = _request_with_host("books.example.com")
    assert oidc_router._frontend_base_url(request) == ""
    response = oidc_router._frontend_success_redirect(request)
    assert response.headers["location"] == "/auth/oidc/callback"


def test_frontend_base_url_uses_loopback_for_local_host(monkeypatch: MonkeyPatch) -> None:
    """Local split-origin development still gets the configured frontend URL."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "http://localhost:5173")

    request = _request_with_host("localhost:8000")
    assert oidc_router._frontend_base_url(request) == "http://localhost:5173"
    response = oidc_router._frontend_success_redirect(request)
    assert response.headers["location"] == "http://localhost:5173/auth/oidc/callback"


def test_frontend_base_url_uses_configured_public_url(monkeypatch: MonkeyPatch) -> None:
    """A real public frontend URL is used for remote requests."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "https://books.example.com/")

    request = _request_with_host("books.example.com")
    assert oidc_router._frontend_base_url(request) == "https://books.example.com"
    response = oidc_router._frontend_success_redirect(request)
    assert response.headers["location"] == "https://books.example.com/auth/oidc/callback"


def test_frontend_base_url_ignores_other_loopback_urls(monkeypatch: MonkeyPatch) -> None:
    """The safety net covers 127.0.0.1 and IPv6 loopback, not just localhost:5173."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "http://127.0.0.1:4173")

    request = _request_with_host("books.example.com")
    assert oidc_router._frontend_base_url(request) == ""


def test_loopback_public_app_url_warns(monkeypatch: MonkeyPatch) -> None:
    """Startup should explain why a loopback PUBLIC_APP_URL is being ignored."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "http://localhost:5173")
    monkeypatch.setattr(settings, "oidc_enabled", True)
    with patch("app.routers.oidc.logger.warning") as mock_warning:
        oidc_router.warn_about_loopback_public_app_url()

    mock_warning.assert_called_once()
    assert "loopback" in str(mock_warning.call_args)


def test_invalid_callback_base_url_warns(monkeypatch: MonkeyPatch) -> None:
    """Startup should explain that a malformed OIDC_CALLBACK_BASE_URL is ignored."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "oidc_callback_base_url", "dev.example.lan:5173")
    with patch("app.routers.oidc.logger.warning") as mock_warning:
        oidc_router.warn_about_invalid_oidc_callback_base_url()

    mock_warning.assert_called_once()
    assert "OIDC_CALLBACK_BASE_URL" in str(mock_warning.call_args)


def test_callback_base_url_warning_is_skipped_when_valid_or_unset(
    monkeypatch: MonkeyPatch,
) -> None:
    """No warning for an empty or well-formed callback base."""
    from app.routers import oidc as oidc_router

    with patch("app.routers.oidc.logger.warning") as mock_warning:
        monkeypatch.setattr(settings, "oidc_callback_base_url", "")
        oidc_router.warn_about_invalid_oidc_callback_base_url()
        monkeypatch.setattr(settings, "oidc_callback_base_url", "https://books.example.com")
        oidc_router.warn_about_invalid_oidc_callback_base_url()

    mock_warning.assert_not_called()


def test_loopback_public_app_url_warning_is_skipped_when_unused(
    monkeypatch: MonkeyPatch,
) -> None:
    """Do not warn about a loopback URL when neither OIDC nor mail uses it."""
    from app.routers import oidc as oidc_router

    monkeypatch.setattr(settings, "public_app_url", "http://localhost:5173")
    monkeypatch.setattr(settings, "oidc_enabled", False)
    monkeypatch.setattr(settings, "mail_server", "")
    with patch("app.routers.oidc.logger.warning") as mock_warning:
        oidc_router.warn_about_loopback_public_app_url()

    mock_warning.assert_not_called()


def test_oidc_login_refreshes_cached_picture(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """A successful OIDC login refreshes the cached picture when selected."""
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "sub-picture",
                "picture": "https://issuer.example/picture.png",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)
    monkeypatch.setattr("app.routers.oidc.is_safe_oidc_picture_url", lambda *_args: True)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    user = session.get(User, user_id)
    assert user is not None
    user.avatar_source = AvatarSource.oidc
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-picture",
        )
    )
    session.commit()

    async def fake_cache(*_args: Any, **_kwargs: Any) -> StoredAvatar:
        return StoredAvatar(filename="1__oidc__abc.webp", content_type="image/webp", byte_size=42)

    monkeypatch.setattr("app.routers.oidc.cache_oidc_avatar", fake_cache)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/oidc/callback"

    image = session.exec(
        select(UserImage).where(UserImage.user_id == user_id, UserImage.variant == "oidc")
    ).first()
    assert image is not None
    assert image.filename == "1__oidc__abc.webp"
    assert image.external_url == "https://issuer.example/picture.png"


def test_oidc_link_caches_picture_without_switching_source(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """Linking caches the provider picture but leaves the selected avatar alone."""
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "sub-link-picture",
                "picture": "https://issuer.example/link.png",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)
    monkeypatch.setattr("app.routers.oidc.is_safe_oidc_picture_url", lambda *_args: True)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]

    async def fake_cache(*_args: Any, **_kwargs: Any) -> StoredAvatar:
        return StoredAvatar(filename="1__oidc__link.webp", content_type="image/webp", byte_size=42)

    monkeypatch.setattr("app.routers.oidc.cache_oidc_avatar", fake_cache)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200
    callback = client.get("/api/oidc/link-callback?code=abc", follow_redirects=False)
    assert callback.status_code == 302

    image = session.exec(
        select(UserImage).where(UserImage.user_id == user_id, UserImage.variant == "oidc")
    ).first()
    assert image is not None
    assert image.external_url == "https://issuer.example/link.png"

    user = session.get(User, user_id)
    assert user is not None
    assert user.avatar_source == AvatarSource.animal


def test_oidc_login_caches_picture_for_existing_animal_avatar(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """Users on the animal avatar get the OIDC picture cached on next login."""
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "sub-animal-picture",
                "picture": "https://issuer.example/animal.png",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)
    monkeypatch.setattr("app.routers.oidc.is_safe_oidc_picture_url", lambda *_args: True)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-animal-picture",
        )
    )
    session.commit()

    async def fake_cache(*_args: Any, **_kwargs: Any) -> StoredAvatar:
        from pathlib import Path

        avatars_dir = Path(settings.avatars_dir)
        avatars_dir.mkdir(parents=True, exist_ok=True)
        (avatars_dir / "1__oidc__animal.webp").write_bytes(b"data")
        return StoredAvatar(filename="1__oidc__animal.webp", content_type="image/webp", byte_size=4)

    monkeypatch.setattr("app.routers.oidc.cache_oidc_avatar", fake_cache)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302

    options = client.get("/api/profile/avatar").json()
    assert options["has_oidc_avatar"] is True
    assert options["source"] == "animal"


def test_oidc_login_accepts_picture_on_provider_host(
    client: TestClient,
    session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """A picture on the provider's own private host is trusted."""
    _set_oidc_enabled(monkeypatch)
    monkeypatch.setattr("app.routers.oidc.oidc_provider_host", lambda: "127.0.0.1")
    fake = FakeOidcClient(
        token={
            "userinfo": {
                "sub": "sub-provider-host",
                "picture": "https://127.0.0.1/picture.png",
            }
        }
    )
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_id="test-oidc",
            oidc_sub="sub-provider-host",
        )
    )
    session.commit()

    seen: dict[str, Any] = {}

    async def fake_cache(*_args: Any, **kwargs: Any) -> StoredAvatar:
        seen.update(kwargs)
        return StoredAvatar(filename="1__oidc__host.webp", content_type="image/webp", byte_size=42)

    monkeypatch.setattr("app.routers.oidc.cache_oidc_avatar", fake_cache)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert seen["trusted_private_host"] == "127.0.0.1"

    image = session.exec(
        select(UserImage).where(UserImage.user_id == user_id, UserImage.variant == "oidc")
    ).first()
    assert image is not None
    assert image.external_url == "https://127.0.0.1/picture.png"
