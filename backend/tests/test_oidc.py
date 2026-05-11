from urllib.parse import parse_qs, urlparse

from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models import OidcLink


class FakeOidcClient:
    def __init__(self, *, token: dict | None = None, redirect_target: str = "https://issuer.example/auth"):
        self._token = token or {}
        self._redirect_target = redirect_target
        self.last_redirect_uri: str | None = None

    async def authorize_access_token(self, _request):
        return self._token

    async def authorize_redirect(self, _request, redirect_uri: str):
        self.last_redirect_uri = redirect_uri
        return RedirectResponse(url=self._redirect_target, status_code=302)


def _set_oidc_enabled(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.oidc.oidc_is_enabled", lambda: True)
    monkeypatch.setattr(settings, "oidc_provider_id", "test-oidc")
    monkeypatch.setattr(settings, "oidc_provider_name", "Test SSO")


def test_oidc_config_enabled(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)

    response = client.get("/api/oidc/config")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider_id"] == "test-oidc"
    assert data["provider_name"] == "Test SSO"


def test_oidc_login_returns_404_when_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: None)

    response = client.get("/api/oidc/login")

    assert response.status_code == 404
    assert response.json()["detail"] == "OIDC is not enabled"


def test_oidc_callback_unlinked_redirects_to_login_warning(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"sub": "sub-unlinked"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/callback?code=abc", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?oidc_error=")
    assert "not+linked" in response.headers["location"]


def test_oidc_callback_linked_redirects_with_api_key(
    client: TestClient,
    session: Session,
    monkeypatch,
):
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(token={"userinfo": {"sub": "sub-linked"}})
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_name="Test SSO",
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
    params = parse_qs(parsed.query)
    assert "api_key" in params
    assert params["api_key"][0].startswith("lk_")


def test_oidc_link_status_reports_unlinked(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)

    response = client.get("/api/oidc/link-status")

    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is False
    assert data["provider_name"] == "Test SSO"


def test_oidc_link_status_reports_linked(client: TestClient, session: Session, monkeypatch):
    _set_oidc_enabled(monkeypatch)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_name="Test SSO",
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


def test_oidc_link_start_returns_authorize_redirect_url(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)

    response = client.post("/api/oidc/link")

    assert response.status_code == 200
    assert response.json()["redirect_url"] == "/api/oidc/link/authorize"


def test_oidc_link_authorize_requires_link_session(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient()
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    response = client.get("/api/oidc/link/authorize", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/oidc/link-callback?error=")


def test_oidc_link_authorize_redirects_to_provider_after_start(client: TestClient, monkeypatch):
    _set_oidc_enabled(monkeypatch)
    fake = FakeOidcClient(redirect_target="https://issuer.example/authorize")
    monkeypatch.setattr("app.routers.oidc.get_oidc_client", lambda: fake)

    start = client.post("/api/oidc/link")
    assert start.status_code == 200

    authorize = client.get("/api/oidc/link/authorize", follow_redirects=False)

    assert authorize.status_code == 302
    assert authorize.headers["location"] == "https://issuer.example/authorize"


def test_oidc_link_callback_creates_link(client: TestClient, session: Session, monkeypatch):
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
    create_user_with_key,
    monkeypatch,
):
    _set_oidc_enabled(monkeypatch)

    other_user, _ = create_user_with_key(email="other-oidc@example.com")
    session.add(
        OidcLink(
            user_id=other_user.id,
            provider_name="Test SSO",
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


def test_oidc_unlink_removes_existing_link(client: TestClient, session: Session, monkeypatch):
    _set_oidc_enabled(monkeypatch)

    me = client.get("/api/auth/me")
    user_id = me.json()["id"]
    session.add(
        OidcLink(
            user_id=user_id,
            provider_name="Test SSO",
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
