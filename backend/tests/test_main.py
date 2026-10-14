"""Tests for app.main module-level code and lifespan helpers."""

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, Response


def test_periodic_maintenance_logs_success() -> None:
    """Successful cleanup should log info and reset failures."""
    from app.main import _periodic_maintenance

    async def _run() -> MagicMock:
        with patch("app.main.cleanup_temp_files"):
            with patch("app.main.cleanup_orphan_covers", return_value=0):
                with patch("app.database.get_session"):
                    with patch("app.main.asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
                        with patch("app.main.logger") as mock_logger:
                            try:
                                await _periodic_maintenance()
                            except asyncio.CancelledError:
                                pass
        return mock_logger

    mock_logger = asyncio.run(_run())
    assert mock_logger.info.call_count == 1
    assert "cleanup completed" in str(mock_logger.info.call_args_list[0])


def test_periodic_maintenance_logs_success_with_orphan_covers() -> None:
    """Orphaned cover cleanup should log when files are deleted."""
    from app.main import _periodic_maintenance

    async def _run() -> MagicMock:
        with patch("app.main.cleanup_temp_files"):
            with patch("app.main.cleanup_orphan_covers", return_value=3):
                with patch("app.database.get_session"):
                    with patch("app.main.asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
                        with patch("app.main.logger") as mock_logger:
                            try:
                                await _periodic_maintenance()
                            except asyncio.CancelledError:
                                pass
        return mock_logger

    mock_logger = asyncio.run(_run())
    assert mock_logger.info.call_count == 2
    assert "orphaned cover cleanup" in str(mock_logger.info.call_args_list[1]).lower()


def test_periodic_maintenance_logs_warning_on_first_failure() -> None:
    """First failure should log a warning."""
    from app.main import _periodic_maintenance

    async def _run() -> MagicMock:
        with patch("app.main.cleanup_temp_files", side_effect=RuntimeError("boom")):
            with patch("app.main.asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
                with patch("app.main.logger") as mock_logger:
                    try:
                        await _periodic_maintenance()
                    except asyncio.CancelledError:
                        pass
        return mock_logger

    mock_logger = asyncio.run(_run())
    assert mock_logger.warning.call_count == 1
    assert "maintenance failed" in str(mock_logger.warning.call_args_list[0]).lower()


def test_periodic_maintenance_logs_error_after_three_failures() -> None:
    """Three consecutive failures should log an error."""
    from app.main import _periodic_maintenance

    async def _run() -> MagicMock:
        with patch("app.main.cleanup_temp_files", side_effect=RuntimeError("boom")):
            with patch("app.main.asyncio.sleep", side_effect=[None, None, None, asyncio.CancelledError()]):
                with patch("app.main.logger") as mock_logger:
                    try:
                        await _periodic_maintenance()
                    except asyncio.CancelledError:
                        pass
        return mock_logger

    mock_logger = asyncio.run(_run())
    assert mock_logger.error.call_count == 1
    assert "consecutively" in str(mock_logger.error.call_args_list[0]).lower()


def test_cookie_samesite_invalid_value_falls_back_to_lax() -> None:
    """An invalid auth_cookie_samesite value should fall back to 'lax'."""
    from app.config import settings
    import app.main as main_module

    original_value = settings.auth_cookie_samesite
    try:
        settings.auth_cookie_samesite = "INVALID"
        importlib.reload(main_module)
        assert main_module.cookie_samesite == "lax"
    finally:
        settings.auth_cookie_samesite = original_value
        importlib.reload(main_module)


def test_parse_forwarded_allow_ips_wildcard() -> None:
    """Wildcard ``*`` returns ``{"*"}``."""
    from app.main import _parse_forwarded_allow_ips

    assert _parse_forwarded_allow_ips("*") == {"*"}
    assert _parse_forwarded_allow_ips(" * ") == {"*"}


def test_parse_forwarded_allow_ips_specific_ips() -> None:
    """Comma/space-separated IPs are parsed into a set."""
    from app.main import _parse_forwarded_allow_ips

    assert _parse_forwarded_allow_ips("10.0.0.1, 10.0.0.2") == {"10.0.0.1", "10.0.0.2"}
    assert _parse_forwarded_allow_ips("10.0.0.1 10.0.0.2") == {"10.0.0.1", "10.0.0.2"}


def test_parse_forwarded_allow_ips_empty() -> None:
    """Empty string returns an empty set."""
    from app.main import _parse_forwarded_allow_ips

    assert _parse_forwarded_allow_ips("") == set()


@pytest.mark.anyio
async def test_proxy_headers_middleware_sets_scheme_from_forwarded_proto() -> None:
    """When forwarded_allow_ips is * and X-Forwarded-Proto is set, scheme should be updated."""
    from app.main import proxy_headers_middleware

    app = FastAPI()

    @app.get("/scheme")
    async def scheme(request: Request):
        return {"scheme": request.url.scheme}

    app.add_middleware(type(None), middleware=proxy_headers_middleware)  # ty: ignore[invalid-argument-type]

    # We need to add the middleware as a pure "http" middleware, which isn't
    # directly doable via add_middleware. Instead, we test the logic directly.
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/scheme",
        "headers": [
            (b"x-forwarded-proto", b"https"),
            (b"host", b"example.com"),
        ],
        "scheme": "http",
        "client": ("10.0.0.1", 54321),
    }
    received: dict | None = None

    async def call_next(request: Request) -> Response:
        nonlocal received
        received = {"scheme": request.url.scheme}
        return JSONResponse(received)

    request = Request(scope)
    response = await proxy_headers_middleware(request, call_next)
    assert received is not None
    assert received["scheme"] == "https"


@pytest.mark.anyio
async def test_proxy_headers_middleware_skips_when_no_header() -> None:
    """When X-Forwarded-Proto is absent, scheme should remain unchanged."""
    from app.main import proxy_headers_middleware

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"example.com")],
        "scheme": "http",
        "client": ("10.0.0.1", 54321),
    }
    received: dict | None = None

    async def call_next(request: Request) -> Response:
        nonlocal received
        received = {"scheme": request.url.scheme}
        return JSONResponse(received)

    request = Request(scope)
    await proxy_headers_middleware(request, call_next)
    assert received is not None
    assert received["scheme"] == "http"


# ── Import source startup validation ───────────────────────────────────────────

def _import_source_flags() -> list[str]:
    """Every per-source enable flag, derived from the registry itself."""
    from app.services import book_import

    return [f"{spec.stage}_import_search_enabled" for spec in book_import._build_sources("")]


@pytest.mark.anyio
async def test_lifespan_refuses_to_start_without_any_import_source(monkeypatch) -> None:
    """Disabling every book import source must stop startup with an actionable error."""
    from app.config import settings
    from app.services import book_import
    import app.main as main_module

    for flag in _import_source_flags():
        monkeypatch.setattr(settings, flag, False)
    monkeypatch.setattr(settings, "google_books_import_search_enabled", False)

    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with pytest.raises(RuntimeError) as exc_info:
            async with main_module.lifespan(main_module.app):
                pass

    message = str(exc_info.value)
    assert "No usable book import source" in message
    # The error must name the variables the operator can set.
    for stage in (s.stage for s in book_import._build_sources("")):
        assert f"{stage.upper()}_IMPORT_SEARCH_ENABLED" in message


def test_credentialed_sources_keep_true_default_for_backward_compatibility() -> None:
    """Every source keeps a built-in default of true.

    Upgrading must never silently drop a source that worked before these switches
    existed. Hardcover and Google Books are skipped anyway when their key or token is
    empty, so the true default costs nothing; the example config recommends false.
    """
    from app.config import Settings

    defaults = Settings(
        api_key_encryption_key="x" * 32,
        _env_file=None,
    )
    assert defaults.open_library_import_search_enabled is True
    assert defaults.hardcover_import_search_enabled is True
    assert defaults.google_books_import_search_enabled is True
    assert defaults.bnf_import_search_enabled is True
    assert defaults.inventaire_import_search_enabled is True
    assert defaults.library_of_congress_import_search_enabled is True


@pytest.mark.anyio
async def test_lifespan_refuses_credentialed_sources_without_credentials(monkeypatch) -> None:
    """Enabled Hardcover/Google Books without a token/key can answer nothing.

    This configuration must be rejected, otherwise the app starts and silently
    returns no search results forever.
    """
    from app.config import settings
    import app.main as main_module

    for flag in _import_source_flags():
        monkeypatch.setattr(settings, flag, False)
    # Only the two credentialed sources are on, and neither has credentials.
    monkeypatch.setattr(settings, "hardcover_import_search_enabled", True)
    monkeypatch.setattr(settings, "google_books_import_search_enabled", True)
    monkeypatch.setattr(settings, "hardcover_app_api_token", "")
    monkeypatch.setattr(settings, "google_books_api_key", "")

    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with pytest.raises(RuntimeError) as exc_info:
            async with main_module.lifespan(main_module.app):
                pass

    assert "HARDCOVER_APP_API_TOKEN" in str(exc_info.value)
    assert "GOOGLE_BOOKS_API_KEY" in str(exc_info.value)


@pytest.mark.anyio
async def test_lifespan_accepts_enabled_hardcover_with_token(monkeypatch) -> None:
    """An enabled source counts once it actually has its credential."""
    from app.config import settings
    import app.main as main_module

    for flag in _import_source_flags():
        monkeypatch.setattr(settings, flag, False)
    monkeypatch.setattr(settings, "hardcover_import_search_enabled", True)
    monkeypatch.setattr(settings, "hardcover_app_api_token", "token")

    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with patch("app.main._telemetry_heartbeat", new=AsyncMock()):
            async with main_module.lifespan(main_module.app):
                pass


@pytest.mark.anyio
async def test_lifespan_starts_with_a_single_import_source(monkeypatch) -> None:
    """One enabled source is enough to start."""
    from app.config import settings
    import app.main as main_module

    for flag in _import_source_flags():
        monkeypatch.setattr(settings, flag, False)
    monkeypatch.setattr(settings, "google_books_import_search_enabled", False)
    monkeypatch.setattr(settings, "bnf_import_search_enabled", True)

    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with patch("app.main._telemetry_heartbeat", new=AsyncMock()):
            async with main_module.lifespan(main_module.app):
                pass


@pytest.mark.anyio
async def test_lifespan_logs_warning_when_mail_not_configured(monkeypatch) -> None:
    """Lifespan should warn when MAIL_SERVER or MAIL_FROM are not configured."""
    from app.config import settings
    import app.main as main_module

    original_server = settings.mail_server
    original_from = settings.mail_from
    try:
        settings.mail_server = "   "
        settings.mail_from = "   "
        importlib.reload(main_module)
        with patch("app.main.logger") as mock_logger:
            with patch("app.main._periodic_maintenance", new=AsyncMock()):
                async with main_module.lifespan(main_module.app):
                    pass
        warning_messages = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("MAIL_SERVER or MAIL_FROM" in msg for msg in warning_messages)
    finally:
        settings.mail_server = original_server
        settings.mail_from = original_from
        importlib.reload(main_module)


def test_display_version_includes_git_sha_when_not_embedded() -> None:
    """Version display should include the git sha when it is not part of the version string."""
    from app import _build_info
    import app.main as main_module

    original_sha = _build_info.__git_sha__
    original_version = _build_info.__version__
    try:
        _build_info.__git_sha__ = "abcdef1234567890"
        _build_info.__version__ = "1.0.0"
        importlib.reload(main_module)
        assert "abcdef1" in main_module._display_version
    finally:
        _build_info.__git_sha__ = original_sha
        _build_info.__version__ = original_version
        importlib.reload(main_module)
@pytest.mark.anyio
async def test_proxy_headers_middleware_skips_untrusted_proxy(monkeypatch) -> None:
    """When request is not from a trusted proxy, X-Forwarded-Proto is ignored."""
    from app.main import proxy_headers_middleware

    monkeypatch.setattr("app.main._TRUSTED_PROXY_IPS", {"10.0.0.5"})

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"host", b"example.com"),
            (b"x-forwarded-proto", b"https"),
        ],
        "scheme": "http",
        "client": ("192.168.1.1", 54321),
    }
    received: dict | None = None

    async def call_next(request: Request) -> Response:
        nonlocal received
        received = {"scheme": request.url.scheme}
        return JSONResponse(received)

    request = Request(scope)
    await proxy_headers_middleware(request, call_next)
    assert received is not None
    assert received["scheme"] == "http"
