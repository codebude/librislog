"""OIDC / SSO integration — provider registration and client creation."""

from typing import Optional
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from authlib.oauth2.client import OAuth2Client

from app.config import settings


oauth: OAuth = OAuth()
_registered: bool = False


def oidc_is_enabled() -> bool:
    """Return True if OIDC is configured and ready to use."""
    return (
        settings.oidc_enabled
        and bool(settings.oidc_provider_id.strip())
        and bool(settings.oidc_client_id.strip())
        and bool(settings.oidc_client_secret.strip())
        and bool(settings.oidc_well_known_url.strip())
    )


def oidc_provider_host() -> str | None:
    """Return the OIDC provider hostname from the well-known URL."""
    try:
        hostname = urlparse(settings.oidc_well_known_url).hostname
    except ValueError:
        return None
    return hostname.lower() if hostname else None


def get_oidc_client() -> Optional[StarletteOAuth2App]:
    """Return the OIDC client, registering it on first call.

    Returns None if OIDC is not enabled.
    """
    global _registered

    if not oidc_is_enabled():
        return None

    if not _registered:
        oauth.register(
            name=settings.oidc_provider_id,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            server_metadata_url=settings.oidc_well_known_url,
            client_kwargs={"scope": settings.oidc_scope},
        )
        _registered = True

    return oauth.create_client(settings.oidc_provider_id)
