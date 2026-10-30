"""FastAPI application factory and middleware setup."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from app import proxy_auth
from app._build_info import __git_sha__, __version__
from app.auth import start_browser_session
from app.config import settings
from app.logging_config import configure_logging
from app.routers import admin, auth, books, config, cover_candidates, covers, data, docs, embed, health, hygiene, import_, oidc, profile, progress, public_profile, sessions, share_links, statistics, tags, users
from app.services.avatar_storage import cleanup_orphan_avatars
from app.services.cover_storage import cleanup_orphan_covers
from app.services.data_import import cleanup_temp_files
from app.services.telemetry import send_telemetry_once

_TELEMETRY_INTERVAL_SECONDS = 23 * 3600

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


async def _periodic_maintenance(interval_hours: int = 1) -> None:
    """Periodically run background maintenance tasks.

    Runs every *interval_hours* hours. After three consecutive failures the
    log level escalates from warning to error.

    Tasks:
    - Clean up stale temporary import files.
    - Delete orphaned cover files no longer referenced by any book.
    - Delete orphaned avatar files no longer referenced by any user image.

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

                deleted_avatars = await loop.run_in_executor(
                    None, cleanup_orphan_avatars, session
                )
                if deleted_avatars:
                    logger.info(
                        "Orphaned avatar cleanup: deleted %d file(s)",
                        deleted_avatars,
                    )

            failures = 0
        except Exception as exc:
            failures += 1
            if failures >= 3:
                logger.error("Periodic maintenance failed %d times consecutively: %s", failures, exc)
            else:
                logger.warning("Periodic maintenance failed (%d): %s", failures, exc)


async def _telemetry_heartbeat() -> None:
    """Send one telemetry heartbeat at startup, then every 24 hours.

    Telemetry is an installation census, not event tracking. ``send_telemetry_once``
    never raises, so failures cannot interrupt the loop or the application.
    """
    while True:
        try:
            await send_telemetry_once()
        except Exception as exc:  # noqa: BLE001 — telemetry must never interfere
            logger.debug("Telemetry heartbeat failed: %s", exc)
        await asyncio.sleep(_TELEMETRY_INTERVAL_SECONDS)


def _validate_import_sources() -> None:
    """Ensure at least one import search provider can actually answer a query.

    Counting enabled flags alone is not enough: Hardcover and Google Books require a
    token/API key, so being switched on without credentials still means no source can
    answer. This checks for a provider that is both enabled and usable.
    """
    from app.services import book_import

    active: list[str] = []
    for spec in book_import._build_sources(""):
        if not spec.enabled():
            continue
        if spec.stage == "hardcover" and not settings.hardcover_app_api_token.strip():
            continue
        active.append(spec.stage)

    if book_import._google_fallback_enabled() and settings.google_books_api_key.strip():
        active.append("google_books")

    if not active:
        keyless = ", ".join(
            sorted(
                f"{spec.stage.upper()}_IMPORT_SEARCH_ENABLED"
                for spec in book_import._build_sources("")
                if spec.stage not in {"hardcover", "google_books"}
            )
        )
        raise RuntimeError(
            "No usable book import source is configured. "
            f"Set at least one of {keyless} to true, or provide "
            "HARDCOVER_APP_API_TOKEN with HARDCOVER_IMPORT_SEARCH_ENABLED=true, "
            "or GOOGLE_BOOKS_API_KEY with GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=true."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create required directories and start background tasks."""
    _validate_import_sources()
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.avatars_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.import_temp_dir).mkdir(parents=True, exist_ok=True)
    cleanup_temp_files()

    if not settings.mail_server.strip() or not settings.mail_from.strip():
        logger.warning(
            "MAIL_SERVER or MAIL_FROM is not configured — password reset emails will not be sent. "
            "See .env.example for mail setup instructions."
        )

    oidc.warn_about_loopback_public_app_url()

    maintenance_task = asyncio.create_task(_periodic_maintenance())
    telemetry_task = (
        asyncio.create_task(_telemetry_heartbeat()) if not settings.telemetry_disabled else None
    )
    yield
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass
    if telemetry_task is not None:
        telemetry_task.cancel()
        try:
            await telemetry_task
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

def _clean_env_value(value: str) -> str:
    """Strip inline comments and whitespace from an env-var string."""
    return value.split("#", 1)[0].strip()


def _parse_forwarded_allow_ips(value: str) -> set[str]:
    """Parse a comma/space-separated IP allow list."""
    if value.strip() == "*":
        return {"*"}
    return {ip.strip() for ip in value.replace(",", " ").split() if ip.strip()}


cookie_domain_raw: str = _clean_env_value(settings.auth_cookie_domain)
cookie_domain: str | None = cookie_domain_raw or None
cookie_samesite: str = _clean_env_value(settings.auth_cookie_samesite).lower()
if cookie_samesite not in {"lax", "strict", "none"}:
    cookie_samesite = "lax"
cookie_name: str = _clean_env_value(settings.auth_cookie_name) or "librislog_session"

_proxy_auth_ips = proxy_auth.trusted_ips()
_proxy_auth_header = proxy_auth.header_name()

if settings.trusted_proxy_auth_enabled:
    if not _proxy_auth_ips:
        logger.warning(
            "TRUSTED_PROXY_AUTH_ENABLED is true but TRUSTED_PROXY_AUTH_IPS is empty; "
            "trusted proxy authentication is disabled"
        )
    elif not _proxy_auth_header:
        logger.warning(
            "TRUSTED_PROXY_AUTH_ENABLED is true but TRUSTED_PROXY_AUTH_HEADER is empty; "
            "trusted proxy authentication is disabled"
        )
    elif "*" in _proxy_auth_ips:
        logger.warning(
            "TRUSTED_PROXY_AUTH_IPS contains '*'; trusted proxy authentication trusts any "
            "client and is unsafe outside an isolated network"
        )

    # Parse the optional mapping at startup so invalid entries are logged once.
    _ = proxy_auth.user_map()

    if not proxy_auth.secret():
        logger.warning(
            "TRUSTED_PROXY_AUTH_SECRET is not set; anyone who can reach the backend directly "
            "and spoof the identity header could impersonate a user"
        )
    if "*" in _parse_forwarded_allow_ips(settings.forwarded_allow_ips):
        logger.warning(
            "FORWARDED_ALLOW_IPS contains '*'; uvicorn may rewrite request.client from "
            "X-Forwarded-For, so the trusted proxy IP check can be bypassed"
        )


# This middleware must be registered before SessionMiddleware so that
# SessionMiddleware wraps it and request.session is available inside.
@app.middleware("http")
async def trusted_proxy_auth_middleware(request: Request, call_next) -> Response:
    """Auto-authenticate a user forwarded by a trusted reverse proxy."""
    if not settings.trusted_proxy_auth_enabled:
        return await call_next(request)

    allow_ips = proxy_auth.trusted_ips()
    configured_header = proxy_auth.header_name()
    if not allow_ips or not configured_header:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    client = request.client
    if client is None or not proxy_auth.ip_is_trusted(client.host, allow_ips):
        return await call_next(request)

    required_secret = proxy_auth.secret()
    if required_secret:
        provided_secret = request.headers.get(proxy_auth.SECRET_HEADER_NAME, "")
        if not secrets.compare_digest(provided_secret, required_secret):
            return await call_next(request)

    forwarded_user = request.headers.get(configured_header, "").strip()
    if not forwarded_user:
        return await call_next(request)

    claimed_email = proxy_auth.effective_identity(forwarded_user)
    if (
        request.session.get("user_id") is not None
        and request.session.get("proxy_auth_email") == claimed_email
    ):
        return await call_next(request)

    try:
        user = await run_in_threadpool(proxy_auth.resolve_user, forwarded_user)
    except Exception:  # noqa: BLE001 — proxy auth must fail closed, never break the request
        logger.warning("Trusted proxy user lookup failed", exc_info=True)
        return await call_next(request)

    if user is None:
        logger.debug("Trusted proxy header did not match exactly one existing user")
        return await call_next(request)

    existing_id = request.session.get("user_id")
    if existing_id == user.id:
        request.session["proxy_auth_email"] = claimed_email
        return await call_next(request)
    if existing_id is not None:
        # Remove only authentication keys so an in-flight OIDC state survives.
        for key in ("user_id", "csrf_token", "credentials_version"):
            request.session.pop(key, None)
    start_browser_session(request, user.id, user.credentials_version)
    request.session["proxy_auth_email"] = claimed_email
    logger.debug("Authenticated user %s via trusted proxy header", user.id)
    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.api_key_encryption_key,
    session_cookie=cookie_name,
    same_site=cookie_samesite,
    https_only=settings.auth_cookie_secure,
    domain=cookie_domain,
)


_FORWARDED_PROTO_TRUSTED_IPS = _parse_forwarded_allow_ips(settings.forwarded_allow_ips)


@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next) -> Response:
    """Respect ``X-Forwarded-Proto`` from trusted proxies to fix URL scheme.

    Without this middleware, ``request.url.scheme`` stays ``http`` when a TLS
    termination proxy (e.g. Traefik) forwards requests to the backend on HTTP.
    That breaks OIDC flows because Authlib validates the redirect URI against
    ``request.url``.
    """
    if "*" in _FORWARDED_PROTO_TRUSTED_IPS or (
        request.client and request.client.host in _FORWARDED_PROTO_TRUSTED_IPS
    ):
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            logger.debug("X-Forwarded-Proto=%s — patching scheme to %s", forwarded_proto, forwarded_proto)
            request.scope["scheme"] = forwarded_proto
        else:
            logger.debug("No X-Forwarded-Proto header received — keeping scheme=%s", request.scope.get("scheme", "unknown"))
    else:
        logger.debug("Request not from trusted proxy (client=%s) — skipping X-Forwarded-Proto check", request.client)
    return await call_next(request)


# Register CORS last so it is the outermost middleware and can add headers to
# every response, including requests handled by the proxy-auth middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


app.include_router(books.router)
app.include_router(sessions.router)
app.include_router(import_.router)
app.include_router(covers.router)
app.include_router(cover_candidates.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(share_links.router)
app.include_router(public_profile.router)
app.include_router(oidc.router)
app.include_router(progress.router)
app.include_router(docs.router)
app.include_router(health.router)
app.include_router(hygiene.router)
app.include_router(tags.router)
app.include_router(statistics.router)
app.include_router(data.router)
app.include_router(config.router)
if settings.embed_enabled:
    app.include_router(embed.router)
app.include_router(admin.router)
