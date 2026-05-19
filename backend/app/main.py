import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.routers import auth, books, covers, data, docs, health, import_, oidc, profile, progress, statistics, users
from app.services.data_import import cleanup_temp_files

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


async def _periodic_temp_cleanup(interval_hours: int = 1) -> None:
    loop = asyncio.get_running_loop()
    failures = 0
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            await loop.run_in_executor(None, cleanup_temp_files)
            logger.info("Periodic temp file cleanup completed")
            failures = 0
        except Exception as exc:
            failures += 1
            if failures >= 3:
                logger.error("Temp file cleanup failed %d times consecutively: %s", failures, exc)
            else:
                logger.warning("Temp file cleanup failed (%d): %s", failures, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.covers_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.import_temp_dir).mkdir(parents=True, exist_ok=True)
    cleanup_temp_files()

    cleanup_task = asyncio.create_task(_periodic_temp_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


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
app.include_router(statistics.router)
app.include_router(data.router)
