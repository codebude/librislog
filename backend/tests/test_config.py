"""Tests for app configuration validation."""

from typing import Any

import pytest


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
