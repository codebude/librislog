"""FastAPI application factory and middleware setup."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from app._build_info import __git_sha__, __version__
from app.config import settings
from app.logging_config import configure_logging
from app.routers import admin, auth, books, cover_candidates, covers, data, docs, health, hygiene, import_, oidc, profile, progress, statistics, users
from app.services.cover_storage import cleanup_orphan_covers
from app.services.data_import import cleanup_temp_files

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


async def _periodic_maintenance(interval_hours: int = 1) -> None:
    """Periodically run background maintenance tasks.

    Runs every *interval_hours* hours. After three consecutive failures the
    log level escalates from warning to error.

    Tasks:
    - Clean up stale temporary import files.
    - Delete orphaned cover files no longer referenced by any book.

    Args:
        interval_hours: Hours between cleanup cycles. Defaults to 1.
    """
    from app.database import get_session

    loop = asyncio.get_running_loop()
    failures = 0
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            await loop.run_in_executor(None, cleanup_temp_files)
            logger.info("Periodic temp file cleanup completed")

            with next(get_session()) as session:
                deleted = await loop.run_in_executor(None, cleanup_orphan_covers, session)
                if deleted:
                    logger.info("Orphaned cover cleanup: deleted %d file(s)", deleted)

            failures = 0
        except Exception as exc:
            failures += 1
            if failures >= 3:
                logger.error("Periodic maintenance failed %d times consecutively: %s", failures, exc)
            else:
                logger.warning("Periodic maintenance failed (%d): %s", failures, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create required directories and start background tasks."""
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.import_temp_dir).mkdir(parents=True, exist_ok=True)
    cleanup_temp_files()

    maintenance_task = asyncio.create_task(_periodic_maintenance())
    yield
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass


if __git_sha__ != "unknown" and __version__.find(__git_sha__[:7]) == -1:
    _display_version = f"{__version__} ({__git_sha__[:7]})"
else:
    _display_version = __version__

app = FastAPI(
    title="LibrisLog API",
    description="Backend API for LibrisLog.",
    version=_display_version,
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
    allow_credentials=True,
)


def _clean_env_value(value: str) -> str:
    """Strip inline comments and whitespace from an env-var string."""
    return value.split("#", 1)[0].strip()


cookie_domain_raw: str = _clean_env_value(settings.auth_cookie_domain)
cookie_domain: str | None = cookie_domain_raw or None
cookie_samesite: str = _clean_env_value(settings.auth_cookie_samesite).lower()
if cookie_samesite not in {"lax", "strict", "none"}:
    cookie_samesite = "lax"
cookie_name: str = _clean_env_value(settings.auth_cookie_name) or "librislog_session"
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.api_key_encryption_key,
    session_cookie=cookie_name,
    same_site=cookie_samesite,
    https_only=settings.auth_cookie_secure,
    domain=cookie_domain,
)

def _parse_forwarded_allow_ips(value: str) -> set[str]:
    """Parse the comma/space-separated ``forwarded_allow_ips`` setting."""
    if value.strip() == "*":
        return {"*"}
    return {ip.strip() for ip in value.replace(",", " ").split() if ip.strip()}


_TRUSTED_PROXY_IPS = _parse_forwarded_allow_ips(settings.forwarded_allow_ips)


@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next) -> Response:
    """Respect ``X-Forwarded-Proto`` from trusted proxies to fix URL scheme.

    Without this middleware, ``request.url.scheme`` stays ``http`` when a TLS
    termination proxy (e.g. Traefik) forwards requests to the backend on HTTP.
    That breaks OIDC flows because Authlib validates the redirect URI against
    ``request.url``.
    """
    if "*" in _TRUSTED_PROXY_IPS or (request.client and request.client.host in _TRUSTED_PROXY_IPS):
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            logger.debug("X-Forwarded-Proto=%s — patching scheme to %s", forwarded_proto, forwarded_proto)
            request.scope["scheme"] = forwarded_proto
        else:
            logger.debug("No X-Forwarded-Proto header received — keeping scheme=%s", request.scope.get("scheme", "unknown"))
    else:
        logger.debug("Request not from trusted proxy (client=%s) — skipping X-Forwarded-Proto check", request.client)
    return await call_next(request)


app.include_router(books.router)
app.include_router(import_.router)
app.include_router(covers.router)
app.include_router(cover_candidates.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(oidc.router)
app.include_router(progress.router)
app.include_router(docs.router)
app.include_router(health.router)
app.include_router(hygiene.router)
app.include_router(statistics.router)
app.include_router(data.router)
app.include_router(admin.router)
