"""OIDC SSO endpoints — login, callback, link, unlink, and status."""

import logging
from urllib.parse import quote_plus, urlparse, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.auth import start_browser_session
from app.database import get_session
from app.models import AvatarSource, OidcLink, User
from app.oidc import get_oidc_client, oidc_is_enabled
from app.config import settings
from app.schemas import OidcConfigRead, OidcLinkRead
from app.services.avatar import (
    VARIANT_OIDC,
    VARIANT_UPLOAD,
    get_user_image,
    image_has_file,
    upsert_avatar_image,
)
from app.services.avatar_storage import (
    cache_oidc_avatar,
    delete_avatar_file,
    is_safe_oidc_picture_url,
)
from app.time_utils import utcnow

router = APIRouter(prefix="/api/oidc", tags=["oidc"])
logger = logging.getLogger(__name__)


def _provider_name() -> str:
    """Return the configured OIDC provider display name."""
    return settings.oidc_provider_name


def _provider_id() -> str:
    """Return the configured OIDC provider identifier."""
    return settings.oidc_provider_id


async def _sync_oidc_avatar(
    session: Session,
    user: User,
    picture: str | None,
    *,
    force_cache: bool = False,
) -> str | None:
    """Update the user's OIDC avatar row from a ``picture`` claim.

    Returns the previous filename when it was replaced and should be deleted
    after the transaction commits.
    """
    if user.id is None:
        return None

    existing = get_user_image(session, user.id, VARIANT_OIDC)
    previous = existing.filename if existing else None

    if not picture:
        if existing:
            existing.external_url = None
            session.add(existing)
        return None

    if not is_safe_oidc_picture_url(picture):
        logger.warning("Ignoring unsafe OIDC picture URL: %s", picture)
        return None

    needs_cache = force_cache or user.avatar_source == AvatarSource.oidc
    if not needs_cache and (existing is None or not existing.filename):
        # A user who linked OIDC before this feature existed still has no cached
        # file. Cache it on the next login so the profile can offer the option.
        needs_cache = True

    stored = None
    if needs_cache:
        stored = await cache_oidc_avatar(
            picture,
            settings.avatars_dir,
            user.id,
        )

    upsert_avatar_image(
        session,
        user.id,
        VARIANT_OIDC,
        stored,
        external_url=picture,
    )
    if previous and stored and previous != stored.filename:
        return previous
    return None


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_loopback_host(hostname: str | None) -> bool:
    """Return True for the hostnames browsers use to reach a local machine."""
    return (hostname or "").lower() in _LOOPBACK_HOSTS


def _is_loopback_url(url: str) -> bool:
    """Return True when a configured URL points at a loopback host."""
    try:
        return _is_loopback_host(urlparse(url).hostname)
    except ValueError:
        return False


def _frontend_base_url(request: Request | None = None) -> str:
    """Base URL of the frontend app, used for browser redirects.

    Empty in single-origin (production) deployments, where the backend serves
    the frontend and relative redirects resolve correctly. Set
    ``PUBLIC_APP_URL`` in split-origin (local dev) setups.

    Older ``.env.example`` files shipped ``http://localhost:5173``. If such a
    loopback URL is still configured, it is honored only for requests that
    themselves arrive on a loopback host. Production requests fall back to
    relative redirects instead of sending users to their own localhost.
    """
    base = (settings.public_app_url or "").strip().rstrip("/")
    if not base:
        return ""
    if request is not None and _is_loopback_url(base):
        if not _is_loopback_host(request.url.hostname):
            return ""
    return base


def warn_about_loopback_public_app_url() -> None:
    """Log a startup hint for an old loopback ``PUBLIC_APP_URL`` value."""
    if not (settings.oidc_enabled or settings.mail_server.strip()):
        return
    if _is_loopback_url(settings.public_app_url or ""):
        logger.warning(
            "PUBLIC_APP_URL=%s points to a loopback address. It will only be used "
            "for requests from loopback hosts; production requests use relative "
            "redirects. Remove it or set the public frontend URL.",
            settings.public_app_url,
        )


def _with_frontend_base(path: str, request: Request | None = None) -> str:
    base = _frontend_base_url(request)
    return f"{base}{path}" if base else path


def _frontend_warning_redirect(message: str, request: Request) -> RedirectResponse:
    """Redirect to the frontend login page with an OIDC error message."""
    return RedirectResponse(
        url=_with_frontend_base(f"/login?oidc_error={quote_plus(message)}", request),
        status_code=302,
    )


def _frontend_success_redirect(request: Request) -> RedirectResponse:
    """Redirect to the frontend callback page on successful login."""
    return RedirectResponse(
        url=_with_frontend_base("/auth/oidc/callback", request),
        status_code=302,
    )


def _link_success_redirect(request: Request) -> RedirectResponse:
    """Redirect to the frontend link callback with success status."""
    return RedirectResponse(
        url=_with_frontend_base("/auth/oidc/link-callback?status=success", request),
        status_code=302,
    )


def _link_error_redirect(message: str, request: Request) -> RedirectResponse:
    """Redirect to the frontend link callback with an error message."""
    return RedirectResponse(
        url=_with_frontend_base(f"/auth/oidc/link-callback?error={quote_plus(message)}", request),
        status_code=302,
    )


def _callback_base_url() -> str:
    """Return the configured OIDC callback origin, or an empty string."""
    return (settings.oidc_callback_base_url or "").strip().rstrip("/")


def _is_valid_callback_base_url(base: str) -> bool:
    """A usable base is an absolute http(s) URL without a path of its own."""
    parts = urlparse(base)
    return parts.scheme in {"http", "https"} and bool(parts.netloc) and parts.path in {"", "/"}


def warn_about_invalid_oidc_callback_base_url() -> None:
    """Log a startup hint when ``OIDC_CALLBACK_BASE_URL`` cannot be used."""
    base = _callback_base_url()
    if base and not _is_valid_callback_base_url(base):
        logger.warning(
            "OIDC_CALLBACK_BASE_URL=%s is not an absolute http(s) URL such as "
            "https://books.example.com; OIDC callbacks fall back to the request host.",
            base,
        )


def _resolve_callback_redirect_uri(request: Request, route_name: str) -> str:
    """Resolve the callback redirect URI via the ASGI router.

    The ``proxy_headers_middleware`` in ``main.py`` already patches
    ``request.scope["scheme"]`` from ``X-Forwarded-Proto``, so
    ``url_for`` returns the correct scheme (``https``) behind a TLS
    termination proxy.

    ``OIDC_CALLBACK_BASE_URL`` replaces the public scheme and host when the
    backend sees a different origin than the browser, for example behind the
    Vite dev proxy, which rewrites the Host header to ``localhost``.
    """
    callback_url = request.url_for(route_name)
    base = _callback_base_url()
    if not base:
        return str(callback_url)
    if not _is_valid_callback_base_url(base):
        logger.warning(
            "Ignoring invalid OIDC_CALLBACK_BASE_URL=%s; using the request host", base
        )
        return str(callback_url)
    parts = urlparse(base)
    return urlunsplit((parts.scheme, parts.netloc, callback_url.path, "", ""))


@router.get("/config", response_model=OidcConfigRead)
def oidc_config() -> OidcConfigRead:
    """Return whether OIDC is enabled and the provider display info."""
    if not oidc_is_enabled():
        return OidcConfigRead(enabled=False)
    return OidcConfigRead(
        enabled=True,
        provider_id=settings.oidc_provider_id,
        provider_name=_provider_name(),
        auto_redirect=settings.oidc_auto_redirect and not settings.password_login_enabled,
    )


@router.get("/login")
async def oidc_login(request: Request):
    """Initiate the OIDC login flow by redirecting to the provider."""
    client = get_oidc_client()
    if not client:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    redirect_uri = _resolve_callback_redirect_uri(request, "oidc_callback")
    try:
        return await client.authorize_redirect(request, redirect_uri)
    except Exception:
        logger.exception(
            "OIDC login redirect failed: provider=%s redirect_uri=%s",
            _provider_id(), redirect_uri,
        )
        return _frontend_warning_redirect(
            f"{_provider_name()} login is currently unavailable. "
            f"Please use email and password, then try again later.",
            request,
        )


@router.get("/callback", name="oidc_callback")
async def oidc_callback(
    request: Request,
    session: Session = Depends(get_session),
):
    """Handle the OIDC login callback from the provider.

    Looks up the OidcLink by provider_id + sub and starts a browser session
    for the linked user.
    """
    client = get_oidc_client()
    if not client:
        logger.warning("OIDC callback called while OIDC disabled")
        return _frontend_warning_redirect("OIDC is not enabled", request)

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        state = request.query_params.get("state", "")
        logger.debug(
            "OIDC callback failed: host=%s scheme=%s cookies=%s state_in_session=%s",
            request.url.hostname,
            request.url.scheme,
            sorted(request.cookies.keys()),
            bool(state) and f"_state_{_provider_id()}_{state}" in request.session,
        )
        logger.exception("OIDC authorize_access_token failed during login callback")
        return _frontend_warning_redirect("OIDC login failed", request)

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        logger.warning("OIDC callback missing sub claim: token_keys=%s", list(token.keys()))
        return _frontend_warning_redirect("OIDC response is missing subject", request)

    link = session.exec(
        select(OidcLink).where(
            OidcLink.provider_id == _provider_id(),
            OidcLink.oidc_sub == oidc_sub,
        )
    ).first()
    if not link:
        logger.info(
            "OIDC login rejected because account not linked: provider=%s sub=%s",
            _provider_id(), oidc_sub,
        )
        return _frontend_warning_redirect(
            f"Your {_provider_name()} account is not linked. "
            f"Please log in with email and password first, then link it in your profile.",
            request,
        )

    user = session.get(User, link.user_id)
    if not user:
        logger.error("OIDC link points to missing user: link_id=%s user_id=%s", link.id, link.user_id)
        return _frontend_warning_redirect("Linked user account no longer exists", request)
    assert user.id is not None

    replaced = await _sync_oidc_avatar(session, user, userinfo.get("picture"))
    session.commit()
    if replaced:
        delete_avatar_file(replaced, settings.avatars_dir)

    start_browser_session(request, user.id, user.credentials_version)
    return _frontend_success_redirect(request)


@router.get("/link-status", response_model=OidcLinkRead)
def oidc_link_status(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> OidcLinkRead:
    """Return the OIDC link status for the current user."""
    if not oidc_is_enabled():
        return OidcLinkRead(linked=False)

    link = session.exec(select(OidcLink).where(OidcLink.user_id == current_user.id)).first()
    if not link:
        return OidcLinkRead(linked=False, provider_name=_provider_name())

    return OidcLinkRead(
        linked=True,
        provider_name=_provider_name(),
        oidc_email=link.oidc_email,
        oidc_name=link.oidc_name,
    )


@router.post("/link")
async def oidc_link_start(
    request: Request,
    current_user: User = Depends(require_user),
) -> dict:
    """Start the OIDC account-linking flow by storing the user_id in the session."""
    if not oidc_is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    request.session["oidc_link_user_id"] = current_user.id
    return {"redirect_url": "/api/oidc/link/authorize"}


@router.get("/link/authorize")
async def oidc_link_authorize(request: Request):
    """Redirect to the OIDC provider to authorize account linking."""
    client = get_oidc_client()
    if not client:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    if not request.session.get("oidc_link_user_id"):
        logger.warning("OIDC link authorize called without link session")
        return _link_error_redirect("Missing link session. Please start linking again.", request)

    redirect_uri = _resolve_callback_redirect_uri(request, "oidc_link_callback")
    try:
        return await client.authorize_redirect(request, redirect_uri)
    except Exception:
        logger.exception(
            "OIDC link authorize redirect failed: provider=%s redirect_uri=%s",
            _provider_id(), redirect_uri,
        )
        return _link_error_redirect(
            "OIDC provider is currently unavailable. Please try again later.",
            request,
        )


@router.get("/link-callback", name="oidc_link_callback")
async def oidc_link_callback(
    request: Request,
    session: Session = Depends(get_session),
):
    """Complete the OIDC account-linking flow.

    Creates or updates the OidcLink record for the current user.
    """
    client = get_oidc_client()
    if not client:
        logger.warning("OIDC link callback called while OIDC disabled")
        return _link_error_redirect("OIDC is not enabled", request)

    user_id = request.session.pop("oidc_link_user_id", None)
    if not user_id:
        logger.warning("OIDC link callback missing link session")
        return _link_error_redirect("Missing link session. Please start linking again.", request)

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        logger.exception("OIDC authorize_access_token failed during link callback")
        return _link_error_redirect("OIDC linking failed", request)

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        logger.warning("OIDC link callback missing sub claim: token_keys=%s", list(token.keys()))
        return _link_error_redirect("OIDC response is missing subject", request)

    existing_by_sub = session.exec(
        select(OidcLink).where(
            OidcLink.provider_id == _provider_id(),
            OidcLink.oidc_sub == oidc_sub,
        )
    ).first()
    if existing_by_sub and existing_by_sub.user_id != user_id:
        logger.warning(
            "OIDC link conflict: provider=%s sub=%s existing_user_id=%s requested_user_id=%s",
            _provider_id(), oidc_sub, existing_by_sub.user_id, user_id,
        )
        return _link_error_redirect("This OIDC account is already linked to another user", request)

    existing_link = session.exec(select(OidcLink).where(OidcLink.user_id == user_id)).first()
    if existing_link:
        existing_link.provider_id = _provider_id()
        existing_link.oidc_sub = oidc_sub
        existing_link.oidc_email = userinfo.get("email")
        existing_link.oidc_name = userinfo.get("name")
        existing_link.linked_at = utcnow()
        session.add(existing_link)
    else:
        session.add(
            OidcLink(
                user_id=user_id,
                provider_id=_provider_id(),
                oidc_sub=oidc_sub,
                oidc_email=userinfo.get("email"),
                oidc_name=userinfo.get("name"),
            )
        )

    linked_user = session.get(User, user_id)
    replaced = None
    if linked_user is not None:
        replaced = await _sync_oidc_avatar(
            session,
            linked_user,
            userinfo.get("picture"),
            force_cache=True,
        )

    session.commit()
    if replaced:
        delete_avatar_file(replaced, settings.avatars_dir)
    return _link_success_redirect(request)


@router.delete("/unlink", status_code=204)
def oidc_unlink(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Unlink the OIDC account from the current user."""
    assert current_user.id is not None
    link = session.exec(select(OidcLink).where(OidcLink.user_id == current_user.id)).first()
    if link:
        session.delete(link)

    oidc_image = get_user_image(session, current_user.id, VARIANT_OIDC)
    removed_filename = oidc_image.filename if oidc_image is not None else None
    if oidc_image is not None:
        session.delete(oidc_image)

    if current_user.avatar_source == AvatarSource.oidc:
        upload = get_user_image(session, current_user.id, VARIANT_UPLOAD)
        current_user.avatar_source = (
            AvatarSource.upload
            if image_has_file(upload, settings.avatars_dir)
            else AvatarSource.animal
        )
        current_user.updated_at = utcnow()
        session.add(current_user)

    session.commit()
    if removed_filename:
        delete_avatar_file(removed_filename, settings.avatars_dir)
