# Plan: Extract `/api/docs`, `/api/redoc`, and `/api/health` from `main.py` into dedicated router modules

## Overview

`backend/app/main.py` (271 lines) currently mixes three distinct concerns:

| Lines | Concern | Purpose |
|-------|---------|---------|
| 1–73 | **App wiring** | FastAPI app creation, CORS, session middleware, router mounting |
| 76–164 | **Custom docs** | `_wrap_docs_html()`, `/api/docs`, `/api/redoc` |
| 167–271 | **Health endpoint** | `/api/health` with 5 sub-checks |

This refactor extracts the docs and health code into their own router modules under `app/routers/`, leaving `main.py` as a ~45-line wiring file.

**Motivation:**
- Single-responsibility modules are easier to test, navigate, and maintain.
- Reduces cognitive load when editing `main.py` — it becomes purely about app configuration and startup.
- Health checks are logically independent and could grow more checks without bloating `main.py`.
- Follows the established pattern of all other routers (`books.py`, `profile.py`, `auth.py`, etc.).

---

## New File: `backend/app/routers/docs.py`

### Design notes
- Uses `request.app` instead of the module-level `app` variable to avoid circular imports. FastAPI's `Request.app` returns the application instance.
- Each module gets its own `logger = logging.getLogger(__name__)` per project convention.
- The helper `_wrap_docs_html` is a pure function — it moves with the routes as a module-private function.

### Full content

```python
import logging

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _wrap_docs_html(html: str) -> HTMLResponse:
    custom_css = """
<style>
  :root {
    --bg: #f4f6f8;
    --surface: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --primary: #2563eb;
    --border: #e5e7eb;
  }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  }
  .topbar, .menu-content {
    display: none !important;
  }
  .swagger-ui .scheme-container,
  .swagger-ui .info,
  .swagger-ui .wrapper {
    background: transparent;
    box-shadow: none;
  }
  .swagger-ui .opblock,
  .swagger-ui .responses-inner,
  .swagger-ui .model-box,
  .swagger-ui .auth-container,
  .swagger-ui .dialog-ux {
    border-color: var(--border);
  }
  .swagger-ui .btn.execute,
  .swagger-ui .btn.authorize,
  .swagger-ui .btn.modal-btn.auth.authorize {
    background: var(--primary);
    border-color: var(--primary);
    color: #fff;
  }
  .swagger-ui .opblock-tag,
  .swagger-ui .opblock-summary,
  .swagger-ui .info .title,
  .swagger-ui,
  .swagger-ui p,
  .swagger-ui table,
  .swagger-ui .response-col_status,
  .swagger-ui .response-col_description {
    color: var(--text);
  }
  .swagger-ui .info .description,
  .swagger-ui .markdown p,
  .swagger-ui .markdown li,
  .swagger-ui .response-col_links,
  .swagger-ui .model-title small {
    color: var(--muted);
  }
  .redoc-wrap {
    background: var(--bg);
  }
  .redoc-wrap > div {
    border-left: 1px solid var(--border);
  }
</style>
"""
    return HTMLResponse(html.replace("</head>", f"{custom_css}</head>"))


@router.get("/api/docs", include_in_schema=False)
def custom_swagger_docs(request: Request) -> HTMLResponse:
    html = get_swagger_ui_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "list",
        },
    ).body.decode("utf-8")
    return _wrap_docs_html(html)


@router.get("/api/redoc", include_in_schema=False)
def custom_redoc_docs(request: Request) -> HTMLResponse:
    html = get_redoc_html(
        openapi_url=request.app.openapi_url,
        title=f"{request.app.title} - ReDoc",
    ).body.decode("utf-8")
    return _wrap_docs_html(html)
```

### Notable change from original
- `custom_swagger_docs` and `custom_redoc_docs` now accept `request: Request` and use `request.app.openapi_url` / `request.app.title` instead of the module-level `app` closure. This is the key design choice that avoids a circular import (`routers/docs.py → main → docs`).

---

## New File: `backend/app/routers/health.py`

### Design notes
- The entire `/api/health` endpoint (body and nested `_result` helper) moves verbatim.
- All imports that were only used by the health endpoint move here: `Depends`, `Session`, `inspect`, `text`, `httpx`, `logging`, `os`, `importlib.metadata`, `Path`, `get_session`, `settings`.
- `logger = logging.getLogger(__name__)` per project convention (replaces the shared `main` logger).

### Full content

```python
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
```

### No semantic changes
The logic, structure, and response shape are identical to the original. Only the import source and logger name change.

---

## Modified File: `backend/app/main.py` (post-refactor)

### Full content

```python
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.routers import auth, books, covers, docs, health, import_, oidc, profile, progress, users

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="LibrisLog API",
    description="Backend API for LibrisLog.",
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean_env_value(value: str) -> str:
    return value.split("#", 1)[0].strip()


cookie_domain_raw = _clean_env_value(settings.auth_cookie_domain)
cookie_domain = cookie_domain_raw or None
cookie_samesite = _clean_env_value(settings.auth_cookie_samesite).lower()
if cookie_samesite not in {"lax", "strict", "none"}:
    cookie_samesite = "lax"
cookie_name = _clean_env_value(settings.auth_cookie_name) or "librislog_session"
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.api_key_encryption_key,
    session_cookie=cookie_name,
    same_site=cookie_samesite,
    https_only=settings.auth_cookie_secure,
    domain=cookie_domain,
)

app.include_router(books.router)
app.include_router(import_.router)
app.include_router(covers.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(oidc.router)
app.include_router(progress.router)
app.include_router(docs.router)
app.include_router(health.router)
```

### Summary of changes from original
| Aspect | Original | Post-refactor |
|--------|----------|---------------|
| Total lines | 271 | ~45 |
| Imports removed | `httpx`, `Depends`, `get_redoc_html`, `get_swagger_ui_html`, `HTMLResponse`, `inspect`, `text`, `Session`, `os`, `importlib.metadata` | — |
| Imports added | — | `docs`, `health` router modules |
| Routes removed | 3 (`/api/docs`, `/api/redoc`, `/api/health`) | — |
| `include_router` calls | 8 | 10 (2 added for `docs`, `health`) |

---

## Test Impact Analysis

### `backend/tests/test_docs.py` — **No changes needed**

The three tests (`test_custom_swagger_docs_available`, `test_custom_redoc_docs_available`, `test_default_docs_disabled`) use `TestClient(app)` and assert HTTP responses. Since the docs routes are still registered on the same `app` object (just via a different router module), they will work identically.

### `backend/tests/test_books.py` — **Updates required in 4 tests**

The health tests patch module-level references in `app.main`. After extraction these symbols move to `app.routers.health`, so the monkeypatch targets must change:

| Test function | Current monkeypatch target | New target |
|---|---|---|
| `test_health_database_down` (line 753) | `monkeypatch.setattr(main_module, "text", fake_text)` | `monkeypatch.setattr("app.routers.health.text", fake_text)` |
| `test_health_missing_tables` (line 770) | `monkeypatch.setattr(main_module, "inspect", lambda bind: FakeInspector())` | `monkeypatch.setattr("app.routers.health.inspect", ...)` |
| `test_health_data_dir_not_writable` (line 790) | `monkeypatch.setattr(main_module.os_module, "access", lambda *a, **kw: False)` | `monkeypatch.setattr("app.routers.health.os_module.access", ...)` |
| `test_health_quote_service_unhealthy` (line 812) | `monkeypatch.setattr(main_module.httpx, "AsyncClient", FakeFailingAsyncClient)` | `monkeypatch.setattr("app.routers.health.httpx.AsyncClient", ...)` |

**Recommended approach:** Use `monkeypatch.setattr("module.attr", value)` string-based form for all four patches, which avoids importing the new module just to patch it. This is the idiomatic pytest approach.

The `import app.main as main_module` lines (used only to get a reference to the module for patching) can be removed from all four tests.

### (Optional) New file: `backend/tests/test_health.py`

The health tests are currently mixed into `test_books.py` (lines 732–825). After extraction, they logically belong in their own file. Moving them is optional — they work fine in either location — but would improve organization. This can be done as a follow-up or skipped entirely.

---

## Implementation Checklist

- [ ] **Create `backend/app/routers/docs.py`** with the full content shown above.
- [ ] **Create `backend/app/routers/health.py`** with the full content shown above.
- [ ] **Edit `backend/app/main.py`**:
  - Remove imports: `httpx`, `Depends`, `get_redoc_html`, `get_swagger_ui_html`, `HTMLResponse`, `inspect`, `text`, `Session`, `os`, `importlib.metadata`, `get_session` from `app.database`.
  - Keep imports: `logging`, `asynccontextmanager`, `Path`, `FastAPI`, `CORSMiddleware`, `SessionMiddleware`, `settings`, `configure_logging`.
  - Add imports: `docs`, `health` to the `from app.routers import ...` line.
  - Remove the `_wrap_docs_html` function + both docs routes (lines 76–164).
  - Remove the `health` function (lines 167–271).
  - Add `app.include_router(docs.router)` and `app.include_router(health.router)`.
- [ ] **Update `backend/tests/test_books.py`**:
  - In `test_health_database_down`: change `monkeypatch.setattr(main_module, "text", ...)` → `monkeypatch.setattr("app.routers.health.text", ...)`. Remove `import app.main as main_module`.
  - In `test_health_missing_tables`: change `monkeypatch.setattr(main_module, "inspect", ...)` → `monkeypatch.setattr("app.routers.health.inspect", ...)`. Remove `import app.main as main_module` and the `original_inspect` line.
  - In `test_health_data_dir_not_writable`: change `monkeypatch.setattr(main_module.os_module, "access", ...)` → `monkeypatch.setattr("app.routers.health.os_module.access", ...)`. Remove `import app.main as main_module`.
  - In `test_health_quote_service_unhealthy`: change `monkeypatch.setattr(main_module.httpx, "AsyncClient", ...)` → `monkeypatch.setattr("app.routers.health.httpx.AsyncClient", ...)`. Remove `import app.main as main_module`.
- [ ] **Run tests** to verify everything passes:
  ```bash
  cd backend && pytest tests/test_docs.py tests/test_books.py -v
  ```
- [ ] **Run the full test suite** to check for regressions:
  ```bash
  cd backend && pytest
  ```

---

## Rollback / Safety

- The new `docs.py` uses `request.app` instead of the module-level `app` closure. This is a safe change — `request.app` is the canonical FastAPI way to access the application instance from within a route handler — but it should be verified by running `test_docs.py`.
- All health endpoint logic is identical — only import paths change. Verify with the existing health tests (after updating monkeypatch targets).
- `_clean_env_value` stays in `main.py` — no change there.

---

## Future Considerations

- If new health checks are added later, they go in `health.py` without touching `main.py`.
- If custom docs styling needs to change, only `docs.py` is modified.
- These routers could gain their own `conftest.py` fixtures if they eventually need specialized test setup.
