"""Tests for app configuration validation and config endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "invalid_settings_kwargs",
    [
        ({"api_key_encryption_key": "   "}, "must be set"),
        ({"api_key_encryption_key": "CHANGE_ME_TO_32PLUS_CHARS"}, "real secret"),
    ],
    indirect=True,
)
def test_api_key_encryption_key_validation(invalid_settings_kwargs: tuple[dict[str, str], str]) -> None:
    """Settings should reject empty or placeholder encryption keys."""
    kwargs, expected_error = invalid_settings_kwargs
    from app.config import Settings

    with pytest.raises(ValueError, match=expected_error):
        Settings(**kwargs)  # ty: ignore[invalid-argument-type]


def test_get_config_returns_feature_flags(client: TestClient, monkeypatch) -> None:
    """GET /api/config should return current feature flag values."""
    monkeypatch.setattr("app.config.settings.embed_enabled", True)
    monkeypatch.setattr("app.config.settings.dashboard_quote_enabled", False)
    monkeypatch.setattr("app.config.settings.thalia_cover_search_enabled", True)
    monkeypatch.setattr("app.config.settings.password_login_enabled", False)
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_enabled", True)
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_ips", "127.0.0.1")
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_header", "X-Forwarded-User")

    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "embed_enabled": True,
        "dashboard_quote_enabled": False,
        "thalia_cover_search_enabled": True,
        "password_login_enabled": False,
        "trusted_proxy_auth_enabled": True,
    }
    assert "trusted_proxy_auth_header" not in data


def test_proxy_auth_flag_is_false_when_misconfigured(client: TestClient, monkeypatch) -> None:
    """An enabled but fail-closed feature must not be advertised as usable."""
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_enabled", True)
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_ips", "")

    assert client.get("/api/config").json()["trusted_proxy_auth_enabled"] is False


def test_proxy_auth_flag_is_false_with_empty_header(client: TestClient, monkeypatch) -> None:
    """An empty header name is the other fail-closed configuration."""
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_enabled", True)
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_ips", "127.0.0.1")
    monkeypatch.setattr("app.config.settings.trusted_proxy_auth_header", "")

    assert client.get("/api/config").json()["trusted_proxy_auth_enabled"] is False
