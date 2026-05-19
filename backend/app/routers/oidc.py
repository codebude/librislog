import logging
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.auth import start_browser_session
from app.database import get_session
from app.models import OidcLink, User
from app.oidc import get_oidc_client, oidc_is_enabled
from app.config import settings
from app.schemas import OidcConfigRead, OidcLinkRead
from app.time_utils import utcnow

router = APIRouter(prefix="/api/oidc", tags=["oidc"])
logger = logging.getLogger(__name__)


def _provider_name() -> str:
    return settings.oidc_provider_name


def _provider_id() -> str:
    return settings.oidc_provider_id


def _frontend_warning_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?oidc_error={quote_plus(message)}", status_code=302)


def _frontend_success_redirect() -> RedirectResponse:
    return RedirectResponse(url="/auth/oidc/callback", status_code=302)


def _link_success_redirect() -> RedirectResponse:
    return RedirectResponse(url="/auth/oidc/link-callback?status=success", status_code=302)


def _link_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/auth/oidc/link-callback?error={quote_plus(message)}", status_code=302)


def _resolve_callback_redirect_uri(request: Request, callback_path: str, route_name: str) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto:
        return f"{forwarded_proto}://{request.headers.get('host')}{callback_path}"
    return str(request.url_for(route_name))


@router.get("/config", response_model=OidcConfigRead)
def oidc_config() -> OidcConfigRead:
    if not oidc_is_enabled():
        return OidcConfigRead(enabled=False)
    return OidcConfigRead(enabled=True, provider_id=settings.oidc_provider_id, provider_name=_provider_name())


@router.get("/login")
async def oidc_login(request: Request):
    client = get_oidc_client()
    if not client:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    redirect_uri = _resolve_callback_redirect_uri(request, "/api/oidc/callback", "oidc_callback")
    try:
        return await client.authorize_redirect(request, redirect_uri)
    except Exception:
        logger.exception("OIDC login redirect failed: provider=%s redirect_uri=%s", _provider_id(), redirect_uri)
        return _frontend_warning_redirect(
            f"{_provider_name()} login is currently unavailable. Please use email and password, then try again later."
        )


@router.get("/callback", name="oidc_callback")
async def oidc_callback(request: Request, session: Session = Depends(get_session)):
    client = get_oidc_client()
    if not client:
        logger.warning("OIDC callback called while OIDC disabled")
        return _frontend_warning_redirect("OIDC is not enabled")

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        logger.exception("OIDC authorize_access_token failed during login callback")
        return _frontend_warning_redirect("OIDC login failed")

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        logger.warning("OIDC callback missing sub claim: token_keys=%s", list(token.keys()))
        return _frontend_warning_redirect("OIDC response is missing subject")

    link = session.exec(
        select(OidcLink).where(OidcLink.provider_id == _provider_id(), OidcLink.oidc_sub == oidc_sub)
    ).first()
    if not link:
        logger.info("OIDC login rejected because account not linked: provider=%s sub=%s", _provider_id(), oidc_sub)
        return _frontend_warning_redirect(
            f"Your {_provider_name()} account is not linked. Please log in with email and password first, then link it in your profile."
        )

    user = session.get(User, link.user_id)
    if not user:
        logger.error("OIDC link points to missing user: link_id=%s user_id=%s", link.id, link.user_id)
        return _frontend_warning_redirect("Linked user account no longer exists")

    start_browser_session(request, user.id)
    return _frontend_success_redirect()


@router.get("/link-status", response_model=OidcLinkRead)
def oidc_link_status(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> OidcLinkRead:
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
async def oidc_link_start(request: Request, current_user: User = Depends(require_user)) -> dict:
    if not oidc_is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    request.session["oidc_link_user_id"] = current_user.id
    return {"redirect_url": "/api/oidc/link/authorize"}


@router.get("/link/authorize")
async def oidc_link_authorize(request: Request):
    client = get_oidc_client()
    if not client:
        raise HTTPException(status_code=404, detail="OIDC is not enabled")

    if not request.session.get("oidc_link_user_id"):
        logger.warning("OIDC link authorize called without link session")
        return _link_error_redirect("Missing link session. Please start linking again.")

    redirect_uri = _resolve_callback_redirect_uri(request, "/api/oidc/link-callback", "oidc_link_callback")
    try:
        return await client.authorize_redirect(request, redirect_uri)
    except Exception:
        logger.exception("OIDC link authorize redirect failed: provider=%s redirect_uri=%s", _provider_id(), redirect_uri)
        return _link_error_redirect("OIDC provider is currently unavailable. Please try again later.")


@router.get("/link-callback", name="oidc_link_callback")
async def oidc_link_callback(request: Request, session: Session = Depends(get_session)):
    client = get_oidc_client()
    if not client:
        logger.warning("OIDC link callback called while OIDC disabled")
        return _link_error_redirect("OIDC is not enabled")

    user_id = request.session.pop("oidc_link_user_id", None)
    if not user_id:
        logger.warning("OIDC link callback missing link session")
        return _link_error_redirect("Missing link session. Please start linking again.")

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        logger.exception("OIDC authorize_access_token failed during link callback")
        return _link_error_redirect("OIDC linking failed")

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        logger.warning("OIDC link callback missing sub claim: token_keys=%s", list(token.keys()))
        return _link_error_redirect("OIDC response is missing subject")

    existing_by_sub = session.exec(
        select(OidcLink).where(OidcLink.provider_id == _provider_id(), OidcLink.oidc_sub == oidc_sub)
    ).first()
    if existing_by_sub and existing_by_sub.user_id != user_id:
        logger.warning(
            "OIDC link conflict: provider=%s sub=%s existing_user_id=%s requested_user_id=%s",
            _provider_id(),
            oidc_sub,
            existing_by_sub.user_id,
            user_id,
        )
        return _link_error_redirect("This OIDC account is already linked to another user")

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

    session.commit()
    return _link_success_redirect()


@router.delete("/unlink", status_code=204)
def oidc_unlink(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    link = session.exec(select(OidcLink).where(OidcLink.user_id == current_user.id)).first()
    if link:
        session.delete(link)
        session.commit()
