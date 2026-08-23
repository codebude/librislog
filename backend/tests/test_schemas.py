"""Tests for Pydantic/SQLModel schemas."""

import pytest

from app.models import Book
from app.schemas import UserSettingsUpdate


def test_book_normalizes_empty_cover_url_to_none() -> None:
    """The Book model validator should turn an empty cover_url string into None."""
    book = Book.model_validate({"title": "Test", "cover_url": ""})
    assert book.cover_url is None


def test_user_settings_update_invalid_theme_raises() -> None:
    """An invalid theme value should raise a validation error."""
    with pytest.raises(ValueError, match="theme must be one of"):
        UserSettingsUpdate(theme="neon")


def test_user_settings_update_blank_custom_theme_returns_none() -> None:
    """A blank custom_theme should be normalized to None."""
    update = UserSettingsUpdate(custom_theme="   ")
    assert update.custom_theme is None


def test_user_settings_update_non_blank_custom_theme_preserved() -> None:
    """A non-blank custom_theme should be preserved."""
    update = UserSettingsUpdate(custom_theme="my-theme")
    assert update.custom_theme == "my-theme"


def test_user_settings_update_valid_theme_accepted() -> None:
    """Valid theme values should be accepted."""
    for theme in ("light", "dark", "custom"):
        update = UserSettingsUpdate(theme=theme)
        assert update.theme == theme


def test_user_settings_update_none_values_accepted() -> None:
    """None values for optional fields should be accepted."""
    update = UserSettingsUpdate()
    assert update.theme is None
    assert update.custom_theme is None
