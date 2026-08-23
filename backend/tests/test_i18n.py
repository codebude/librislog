"""Tests for app.i18n.translate."""

from app.i18n import translate



def test_translate_existing_key() -> None:
    """An existing key returns the translated string."""
    assert translate("email.passwordResetSubject") == "Password Reset – LibrisLog"


def test_translate_missing_key_returns_empty() -> None:
    """A missing key returns an empty string."""
    assert translate("does.not.exist") == ""


def test_translate_fallback_locale() -> None:
    """An unsupported locale falls back to English."""
    assert translate("email.passwordResetSubject", locale="xx") == "Password Reset – LibrisLog"


def test_translate_interpolation() -> None:
    """Placeholders are interpolated into the translated value."""
    body = translate("email.passwordResetBody", duration_minutes="30", reset_url="https://example.com/reset")
    assert "30 minutes" in body
    assert "https://example.com/reset" in body


def test_translate_non_dict_path_returns_empty() -> None:
    """Traversing into a non-dict value returns an empty string."""
    assert translate("email.passwordResetSubject.extra") == ""


def test_translate_invalid_value_returns_empty(monkeypatch) -> None:
    """A non-string leaf value is coerced to an empty string."""
    monkeypatch.setattr("app.i18n._load_translations", lambda locale: {"key": 123})
    assert translate("key") == ""
