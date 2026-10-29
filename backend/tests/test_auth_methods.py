"""Tests for configurable password login and trusted reverse-proxy authentication."""

from collections.abc import Generator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import proxy_auth
from app.auth import get_password_hash
from app.database import get_session
from app.main import app
from app.models import User, UserRole


@pytest.fixture(name="password_login_disabled")
def password_login_disabled_fixture(monkeypatch) -> None:
    """Disable password-based flows for the duration of a test."""
    monkeypatch.setattr("app.config.settings.password_login_enabled", False)


def test_login_rejected_when_password_login_disabled(
    client: TestClient, password_login_disabled: None
) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test-password"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Password login is disabled"


def test_forgot_password_rejected_when_password_login_disabled(
    client: TestClient, password_login_disabled: None
) -> None:
    resp = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Password login is disabled"


def test_reset_password_rejected_when_password_login_disabled(
    client: TestClient, password_login_disabled: None
) -> None:
    resp = client.post(
        "/api/auth/reset-password",
        json={"token": "irrelevant", "password": "Secret123!"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Password login is disabled"


def test_setup_still_bootstraps_when_password_login_disabled(
    session: Session, password_login_disabled: None
) -> None:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as raw_client:
            assert raw_client.get("/api/auth/setup-required").json() == {"required": True}
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
            assert setup.json()["user"]["role"] == "admin"

            me = raw_client.get("/api/auth/me")
            assert me.status_code == 200
            assert me.json()["email"] == "first-admin@example.com"
    finally:
        app.dependency_overrides.clear()


# ── Trusted reverse-proxy authentication ──────────────────────────────────────


@pytest.fixture(name="proxy_auth_enabled")
def proxy_auth_enabled_fixture(monkeypatch, session: Session) -> Session:
    """Enable trusted proxy auth and point the resolver at the in-memory DB."""
    import app.main as main_module

    engine = session.get_bind()
    monkeypatch.setattr(proxy_auth, "_session_factory", lambda: Session(engine))
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_enabled", True)
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "127.0.0.1")
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_header", "X-Forwarded-User")
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_secret", "")
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_user_map", "")
    return session


def _add_user(
    session: Session,
    *,
    email: str,
    firstname: str = "Proxy",
    role: UserRole = UserRole.user,
) -> User:
    user = User(
        firstname=firstname,
        lastname="User",
        email=email,
        role=role,
        hashed_password=get_password_hash("proxy-password"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_proxy_auth_creates_session_from_trusted_header(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"
    assert "set-cookie" in {key.lower() for key in resp.headers}


def test_proxy_auth_ignores_untrusted_client(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "10.0.0.1")
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 401


def test_proxy_auth_ignores_unknown_email(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "nobody@example.com"})
    assert resp.status_code == 401


def test_proxy_auth_disabled_when_ip_list_empty(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "")
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 401

    config = client.get("/api/config").json()
    assert config["trusted_proxy_auth_enabled"] is False


def test_proxy_auth_accepts_wildcard_ip(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "*")
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 200


def test_proxy_auth_requires_configured_secret(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_secret", "s3cret")
    client.headers.pop("X-API-Key", None)

    missing = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert missing.status_code == 401

    wrong = client.get(
        "/api/auth/me",
        headers={"X-Forwarded-User": "test@example.com", proxy_auth.SECRET_HEADER_NAME: "nope"},
    )
    assert wrong.status_code == 401

    correct = client.get(
        "/api/auth/me",
        headers={"X-Forwarded-User": "test@example.com", proxy_auth.SECRET_HEADER_NAME: "s3cret"},
    )
    assert correct.status_code == 200
    assert correct.json()["email"] == "test@example.com"


def test_proxy_auth_fails_closed_when_user_lookup_raises(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    def broken_factory():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(proxy_auth, "_session_factory", broken_factory)
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 401


def test_proxy_auth_skips_lookup_for_same_session_user(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    calls = {"count": 0}
    original = proxy_auth.resolve_user

    def counting_resolver(email: str):
        calls["count"] += 1
        return original(email)

    monkeypatch.setattr(proxy_auth, "resolve_user", counting_resolver)
    client.headers.pop("X-API-Key", None)

    first = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    second = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


def test_proxy_auth_reauthenticates_when_user_changes(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    second = _add_user(proxy_auth_enabled, email="second@example.com", firstname="Second")
    client.headers.pop("X-API-Key", None)

    first = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert first.status_code == 200
    assert first.json()["email"] == "test@example.com"

    second_resp = client.get("/api/auth/me", headers={"X-Forwarded-User": second.email})
    assert second_resp.status_code == 200
    assert second_resp.json()["email"] == "second@example.com"


@pytest.mark.anyio
async def test_proxy_auth_middleware_skips_options_and_missing_client(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_enabled", True)
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "10.0.0.1")
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_header", "X-Forwarded-User")
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_secret", "")

    called = {"count": 0}

    async def call_next(request: Request):
        called["count"] += 1
        return None

    options_scope = {
        "type": "http",
        "method": "OPTIONS",
        "path": "/",
        "headers": [(b"x-forwarded-user", b"test@example.com")],
        "client": ("10.0.0.1", 1234),
        "session": {},
    }
    await main_module.trusted_proxy_auth_middleware(Request(options_scope), call_next)
    assert called["count"] == 1

    no_client_scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-user", b"test@example.com")],
        "client": None,
        "session": {},
    }
    await main_module.trusted_proxy_auth_middleware(Request(no_client_scope), call_next)
    assert called["count"] == 2


def test_proxy_auth_is_inactive_by_default(client: TestClient) -> None:
    """Default configuration must not auto-authenticate anyone."""
    client.headers.pop("X-API-Key", None)
    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 401


def test_proxy_auth_lookup_is_case_insensitive(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    from sqlmodel import select

    expected = proxy_auth_enabled.exec(
        select(User).where(User.email == "test@example.com")
    ).first()
    assert expected is not None

    user = proxy_auth.resolve_user("TEST@EXAMPLE.COM")
    assert user is not None
    assert user.id == expected.id


def test_proxy_auth_lookup_rejects_ambiguous_case_variants(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    _add_user(proxy_auth_enabled, email="TEST@example.com", firstname="Variant")

    assert proxy_auth.resolve_user("test@example.com") is None


def test_proxy_auth_user_mapping_translates_proxy_username(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings,
        "trusted_proxy_auth_user_map",
        "alice=test@example.com",
    )
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_proxy_auth_user_mapping_falls_back_to_header_value(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings,
        "trusted_proxy_auth_user_map",
        "alice=other@example.com",
    )
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "test@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_proxy_auth_user_mapping_is_case_insensitive(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings,
        "trusted_proxy_auth_user_map",
        "ALICE=TEST@EXAMPLE.COM",
    )
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "Alice"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_proxy_auth_user_mapping_unknown_email_is_ignored(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings,
        "trusted_proxy_auth_user_map",
        "alice=nobody@example.com",
    )
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert resp.status_code == 401


def test_proxy_auth_user_map_parsing_skips_invalid_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "alice=alice@example.com, bob=bob@example.com, broken",
    )

    mapping = proxy_auth.user_map()
    assert mapping["alice"] == "alice@example.com"
    assert mapping["bob"] == "bob@example.com"
    assert len(mapping) == 2


def test_proxy_auth_user_map_handles_spaces_and_comments(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "alice = alice@example.com, bob=bob@example.com # household",
    )

    mapping = proxy_auth.user_map()
    assert mapping == {"alice": "alice@example.com", "bob": "bob@example.com"}


def test_proxy_auth_user_map_preserves_hash_inside_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "us#er=alice@example.com",
    )

    mapping = proxy_auth.user_map()
    assert mapping == {"us#er": "alice@example.com"}


def test_proxy_auth_user_map_rejects_equals_inside_value(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "alice==alice@example.com, bob=a@b.c=d, carol=carol@example.com",
    )

    mapping = proxy_auth.user_map()
    assert mapping == {"carol": "carol@example.com"}


def test_proxy_auth_user_map_duplicate_keys_last_wins(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "alice=one@example.com,ALICE=two@example.com",
    )

    mapping = proxy_auth.user_map()
    assert mapping == {"alice": "two@example.com"}


def test_proxy_auth_user_map_ignores_non_email_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.trusted_proxy_auth_user_map",
        "alice=alice@example.com, bob=not-an-email, =missing@example.com, broken",
    )

    mapping = proxy_auth.user_map()
    assert mapping == {"alice": "alice@example.com"}


def test_proxy_auth_unmapped_non_email_fails_closed(
    client: TestClient, proxy_auth_enabled: Session
) -> None:
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "bob"})
    assert resp.status_code == 401


def test_proxy_auth_mapping_does_not_bypass_trusted_ip(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings, "trusted_proxy_auth_user_map", "alice=test@example.com"
    )
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_ips", "10.0.0.1")
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert resp.status_code == 401


def test_proxy_auth_mapping_does_not_bypass_secret(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module.settings, "trusted_proxy_auth_user_map", "alice=test@example.com"
    )
    monkeypatch.setattr(main_module.settings, "trusted_proxy_auth_secret", "s3cret")
    client.headers.pop("X-API-Key", None)

    resp = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert resp.status_code == 401


def test_proxy_auth_mapping_change_forces_reauthentication(
    client: TestClient, proxy_auth_enabled: Session, monkeypatch
) -> None:
    import app.main as main_module

    second = _add_user(proxy_auth_enabled, email="second@example.com", firstname="Second")
    monkeypatch.setattr(
        main_module.settings, "trusted_proxy_auth_user_map", "alice=test@example.com"
    )
    client.headers.pop("X-API-Key", None)

    first = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert first.status_code == 200
    assert first.json()["email"] == "test@example.com"

    monkeypatch.setattr(
        main_module.settings, "trusted_proxy_auth_user_map", f"alice={second.email}"
    )
    switched = client.get("/api/auth/me", headers={"X-Forwarded-User": "alice"})
    assert switched.status_code == 200
    assert switched.json()["email"] == "second@example.com"


def test_proxy_auth_secret_preserves_hash_characters(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_secret", "ab#cd")
    assert proxy_auth.secret() == "ab#cd"


def test_parse_ip_allow_list_supports_cidr_and_ipv6() -> None:
    entries = proxy_auth.parse_ip_allow_list(
        "172.18.0.0/16, 2001:db8::1, ::ffff:192.168.1.5, not-an-ip"
    )

    assert "172.18.0.0/16" in entries
    assert "2001:db8::1" in entries
    assert "192.168.1.5" in entries
    assert proxy_auth.ip_is_trusted("172.18.5.4", entries) is True
    assert proxy_auth.ip_is_trusted("10.0.0.1", entries) is False
    assert proxy_auth.ip_is_trusted(None, entries) is False


def test_proxy_auth_middleware_is_inside_session_middleware() -> None:
    names = []
    for middleware in app.user_middleware:
        cls_name = getattr(middleware.cls, "__name__", str(middleware.cls))
        dispatch = middleware.kwargs.get("dispatch")
        names.append(getattr(dispatch, "__name__", cls_name) if dispatch else cls_name)

    # The list is outermost-first, so SessionMiddleware must appear earlier.
    assert names.index("SessionMiddleware") < names.index("trusted_proxy_auth_middleware")
