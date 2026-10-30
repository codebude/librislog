"""Application-level config endpoint for frontend feature flags."""

from fastapi import APIRouter

from app import proxy_auth
from app.config import settings
from app.schemas import AppConfigRead

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config", response_model=AppConfigRead)
def app_config() -> AppConfigRead:
    """Return application-level feature flags."""
    return AppConfigRead(
        embed_enabled=settings.embed_enabled,
        dashboard_quote_enabled=settings.dashboard_quote_enabled,
        thalia_cover_search_enabled=settings.thalia_cover_search_enabled,
        password_login_enabled=settings.password_login_enabled,
        # Report the effective state: a misconfigured proxy feature is inactive.
        trusted_proxy_auth_enabled=proxy_auth.is_active(),
        avatar_max_upload_mb=settings.avatar_max_upload_mb,
        avatar_max_dimension=settings.avatar_max_dimension,
    )
