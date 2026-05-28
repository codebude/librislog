"""Tests for app.main module-level code and lifespan helpers."""

import asyncio
import importlib
from unittest.mock import MagicMock, patch

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

    app.add_middleware(type(None), middleware=proxy_headers_middleware)  # noqa

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
