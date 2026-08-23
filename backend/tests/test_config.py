"""Tests for app configuration validation and config endpoint."""

from typing import Any

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

    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "embed_enabled": True,
        "dashboard_quote_enabled": False,
        "thalia_cover_search_enabled": True,
    }
