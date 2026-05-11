from datetime import datetime, timezone
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import (
    decrypt_api_key,
    require_user_by_api_key,
)
from app.database import get_session
from app.models import ApiKey, OidcLink, User
from app.oidc import get_oidc_client, oidc_is_enabled
from app.config import settings
from app.schemas import OidcConfigRead, OidcLinkRead

router = APIRouter(prefix="/api/oidc", tags=["oidc"])


def _provider_name() -> str:
    return settings.oidc_provider_name


def _frontend_warning_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?oidc_error={quote_plus(message)}", status_code=302)


def _frontend_success_redirect(api_key: str) -> RedirectResponse:
    return RedirectResponse(url=f"/auth/oidc/callback?api_key={quote_plus(api_key)}", status_code=302)


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
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="oidc_callback")
async def oidc_callback(request: Request, session: Session = Depends(get_session)):
    client = get_oidc_client()
    if not client:
        return _frontend_warning_redirect("OIDC is not enabled")

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        return _frontend_warning_redirect("OIDC login failed")

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        return _frontend_warning_redirect("OIDC response is missing subject")

    link = session.exec(select(OidcLink).where(OidcLink.oidc_sub == oidc_sub)).first()
    if not link:
        return _frontend_warning_redirect(
            f"Your {_provider_name()} account is not linked. Please log in with email and password first, then link it in your profile."
        )

    user = session.get(User, link.user_id)
    if not user:
        return _frontend_warning_redirect("Linked user account no longer exists")

    primary_key = session.exec(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.is_primary.is_(True), ApiKey.revoked_at.is_(None))
    ).first()
    if not primary_key or not primary_key.key_encrypted:
        return _frontend_warning_redirect("Primary API key missing")

    primary_key.last_used_at = datetime.now(timezone.utc)
    session.add(primary_key)
    session.commit()

    return _frontend_success_redirect(decrypt_api_key(primary_key.key_encrypted))


@router.get("/link-status", response_model=OidcLinkRead)
def oidc_link_status(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> OidcLinkRead:
    if not oidc_is_enabled():
        return OidcLinkRead(linked=False)

    link = session.exec(select(OidcLink).where(OidcLink.user_id == current_user.id)).first()
    if not link:
        return OidcLinkRead(linked=False, provider_name=_provider_name())

    return OidcLinkRead(
        linked=True,
        provider_name=link.provider_name,
        oidc_email=link.oidc_email,
        oidc_name=link.oidc_name,
    )


@router.post("/link")
async def oidc_link_start(request: Request, current_user: User = Depends(require_user_by_api_key)) -> dict:
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
        return _link_error_redirect("Missing link session. Please start linking again.")

    redirect_uri = _resolve_callback_redirect_uri(request, "/api/oidc/link-callback", "oidc_link_callback")
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/link-callback", name="oidc_link_callback")
async def oidc_link_callback(request: Request, session: Session = Depends(get_session)):
    client = get_oidc_client()
    if not client:
        return _link_error_redirect("OIDC is not enabled")

    user_id = request.session.pop("oidc_link_user_id", None)
    if not user_id:
        return _link_error_redirect("Missing link session. Please start linking again.")

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        return _link_error_redirect("OIDC linking failed")

    userinfo = token.get("userinfo") or {}
    oidc_sub = userinfo.get("sub")
    if not oidc_sub:
        return _link_error_redirect("OIDC response is missing subject")

    existing_by_sub = session.exec(select(OidcLink).where(OidcLink.oidc_sub == oidc_sub)).first()
    if existing_by_sub and existing_by_sub.user_id != user_id:
        return _link_error_redirect("This OIDC account is already linked to another user")

    existing_link = session.exec(select(OidcLink).where(OidcLink.user_id == user_id)).first()
    if existing_link:
        existing_link.provider_name = _provider_name()
        existing_link.oidc_sub = oidc_sub
        existing_link.oidc_email = userinfo.get("email")
        existing_link.oidc_name = userinfo.get("name")
        existing_link.linked_at = datetime.now(timezone.utc)
        session.add(existing_link)
    else:
        session.add(
            OidcLink(
                user_id=user_id,
                provider_name=_provider_name(),
                oidc_sub=oidc_sub,
                oidc_email=userinfo.get("email"),
                oidc_name=userinfo.get("name"),
            )
        )

    session.commit()
    return _link_success_redirect()


@router.delete("/unlink", status_code=204)
def oidc_unlink(
    current_user: User = Depends(require_user_by_api_key),
    session: Session = Depends(get_session),
) -> None:
    link = session.exec(select(OidcLink).where(OidcLink.user_id == current_user.id)).first()
    if link:
        session.delete(link)
        session.commit()
