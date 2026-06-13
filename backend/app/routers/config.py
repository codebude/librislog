"""Application-level config endpoint for frontend feature flags."""

from fastapi import APIRouter

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
    )
