from authlib.integrations.starlette_client import OAuth

from app.config import settings


oauth = OAuth()
_registered = False


def oidc_is_enabled() -> bool:
    return (
        settings.oidc_enabled
        and bool(settings.oidc_provider_id.strip())
        and bool(settings.oidc_client_id.strip())
        and bool(settings.oidc_client_secret.strip())
        and bool(settings.oidc_well_known_url.strip())
    )


def get_oidc_client():
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
