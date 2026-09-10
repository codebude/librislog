"""Share-link management endpoints — CRUD for a user's public profile links."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.auth import (
    generate_public_profile_token,
    get_public_profile_token_prefix,
    hash_public_profile_token,
    require_user,
)
from app.database import get_session
from app.models import PublicProfileAudience, PublicProfileLink, User
from app.schemas import (
    PublicProfileLinkCreate,
    PublicProfileLinkCreateResponse,
    PublicProfileLinkRead,
    PublicProfileLinkUpdate,
    PublicProfileVisibilityConfig,
    ShareLinkRevealResponse,
)
from app.services.public_profile import (
    parse_visibility_config,
    serialize_visibility_config,
)
from app.time_utils import utcnow

router = APIRouter(prefix="/api/profile/share-links", tags=["share-links"])


def _to_read_model(link: PublicProfileLink) -> PublicProfileLinkRead:
    """Convert a link model to its read schema, parsing the stored config."""
    assert link.id is not None
    return PublicProfileLinkRead(
        id=link.id,
        name=link.name,
        token_prefix=link.token_prefix,
        audience=link.audience,
        visibility_config=parse_visibility_config(link.visibility_config_json),
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


def _get_owned_link(link_id: int, user_id: int, session: Session) -> PublicProfileLink:
    """Fetch a non-revoked link owned by *user_id*, raising 404 otherwise."""
    link = session.get(PublicProfileLink, link_id)
    if not link or link.user_id != user_id or link.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Share link not found")
    return link


def _ensure_future_expiry(expires_at: datetime | None) -> None:
    """Reject expiry dates in the past so links cannot be created already dead."""
    if expires_at is not None and expires_at <= utcnow():
        raise HTTPException(
            status_code=422,
            detail="Expiry date must be in the future",
        )


@router.get("", response_model=list[PublicProfileLinkRead])
def list_share_links(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[PublicProfileLinkRead]:
    """List non-revoked share links for the current user."""
    assert current_user.id is not None
    links = session.exec(
        select(PublicProfileLink)
        .where(
            PublicProfileLink.user_id == current_user.id,
            col(PublicProfileLink.revoked_at).is_(None),
        )
        .order_by(col(PublicProfileLink.created_at).desc())
    ).all()
    return [_to_read_model(link) for link in links]


@router.post("", response_model=PublicProfileLinkCreateResponse, status_code=201)
def create_share_link(
    body: PublicProfileLinkCreate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> PublicProfileLinkCreateResponse:
    """Create a new share link. The raw token is returned exactly once."""
    assert current_user.id is not None
    _ensure_future_expiry(body.expires_at)
    plain_token = generate_public_profile_token()
    audience = PublicProfileAudience(body.audience or PublicProfileAudience.public)
    link = PublicProfileLink(
        user_id=current_user.id,
        name=body.name,
        token_prefix=get_public_profile_token_prefix(plain_token),
        token=plain_token,
        token_hash=hash_public_profile_token(plain_token),
        audience=audience,
        visibility_config_json=serialize_visibility_config(body.visibility_config),
        expires_at=body.expires_at,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return PublicProfileLinkCreateResponse(
        token=plain_token,
        link=_to_read_model(link),
    )


@router.post("/{link_id}/reveal", response_model=ShareLinkRevealResponse)
def reveal_share_link(
    link_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> ShareLinkRevealResponse:
    """Return the raw token for a share link owned by the current user."""
    assert current_user.id is not None
    link = _get_owned_link(link_id, current_user.id, session)
    if not link.token:
        raise HTTPException(status_code=404, detail="Token not available for legacy link")
    return ShareLinkRevealResponse(token=link.token)


@router.patch("/{link_id}", response_model=PublicProfileLinkRead)
def update_share_link(
    link_id: int,
    body: PublicProfileLinkUpdate,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> PublicProfileLinkRead:
    """Update name, audience, visibility config, or expiry of a share link."""
    assert current_user.id is not None
    link = _get_owned_link(link_id, current_user.id, session)

    update_data = body.model_dump(exclude_unset=True)
    if "expires_at" in update_data and update_data["expires_at"] is not None:
        _ensure_future_expiry(update_data["expires_at"])
    if "visibility_config" in update_data:
        update_data["visibility_config_json"] = serialize_visibility_config(
            body.visibility_config or PublicProfileVisibilityConfig()
        )
        update_data.pop("visibility_config")
    link.sqlmodel_update(update_data)
    session.add(link)
    session.commit()
    session.refresh(link)
    return _to_read_model(link)


@router.delete("/{link_id}", status_code=204)
def delete_share_link(
    link_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    """Revoke a share link. Subsequent public access returns 404."""
    assert current_user.id is not None
    link = _get_owned_link(link_id, current_user.id, session)
    link.revoked_at = utcnow()
    session.add(link)
    session.commit()