import logging
import os as os_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlmodel import Session

from app.config import settings
from app.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/health", tags=["meta"])
async def health(db_session: Session = Depends(get_session)) -> dict:
    checks: dict[str, dict] = {}
    overall_healthy = True

    def _result(*, healthy: bool, detail: str | None = None) -> dict:
        return {
            "status": "healthy" if healthy else "unhealthy",
            **( {"detail": detail} if detail else {} ),
        }

    # ── 1. Database connectivity ────────────────────────────────────────────
    db_ok = True
    db_detail = None
    try:
        db_session.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)
        logger.warning("Health check failed — database connectivity: %s", exc)
    checks["database_connectivity"] = _result(healthy=db_ok, detail=db_detail)
    overall_healthy = overall_healthy and db_ok

    # ── 2. Database schema ──────────────────────────────────────────────────
    schema_ok = True
    schema_detail = None
    try:
        inspector = inspect(db_session.bind)
        existing = set(inspector.get_table_names())
        required = {"user", "book"}
        missing = required - existing
        if missing:
            schema_ok = False
            schema_detail = f"Missing tables: {', '.join(sorted(missing))}"
    except Exception as exc:
        schema_ok = False
        schema_detail = str(exc)
        logger.warning("Health check failed — database schema: %s", exc)
    checks["database_schema"] = _result(healthy=schema_ok, detail=schema_detail)
    overall_healthy = overall_healthy and schema_ok

    # ── 3. Data directory writable ──────────────────────────────────────────
    dir_ok = True
    dir_detail = None
    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        if db_url == "sqlite:///:memory:":
            dir_detail = "Skipped — in-memory database"
        else:
            data_path_str = db_url.removeprefix("sqlite:///")
            if "?" in data_path_str:
                data_path_str = data_path_str.split("?", 1)[0]
            data_path = Path(data_path_str)
            data_dir = data_path.parent
            if not data_path.is_absolute():
                data_dir = Path.cwd() / data_dir
            if not data_dir.exists():
                dir_ok = False
                dir_detail = f"Data directory does not exist: {data_dir}"
            elif not os_module.access(str(data_dir), os_module.W_OK):
                dir_ok = False
                dir_detail = f"Data directory is not writable: {data_dir}"
    else:
        dir_detail = "Skipped — not a SQLite database"
    if not dir_ok:
        logger.warning("Health check failed — data directory: %s", dir_detail)
    checks["data_dir_writable"] = _result(healthy=dir_ok, detail=dir_detail)
    overall_healthy = overall_healthy and dir_ok

    # ── 4. Quote service health ────────────────────────────────────────────
    quote_ok = True
    quote_detail = None
    if settings.dashboard_quote_enabled:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(settings.dashboard_quote_url)
                resp.raise_for_status()
        except Exception as exc:
            quote_ok = False
            quote_detail = str(exc)
            logger.warning("Health check failed — quote service: %s", exc)
        checks["quote_service"] = _result(healthy=quote_ok, detail=quote_detail)
    else:
        checks["quote_service"] = {
            "status": "healthy",
            "detail": "Quote service is disabled via configuration",
        }
    overall_healthy = overall_healthy and quote_ok

    # ── 5. App version ──────────────────────────────────────────────────────
    app_ver = "unknown"
    try:
        app_ver = version("librislog-backend")
    except PackageNotFoundError:
        pass

    checks["app_version"] = {
        "version": app_ver,
        "git_sha": os_module.environ.get("GIT_SHA", "unknown"),
    }

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "checks": checks,
    }
