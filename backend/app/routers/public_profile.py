"""Public (unauthenticated) profile data endpoint.

Validates a share-link token, checks expiry and audience rules, and returns a
whitelisted view of the owner's profile. Private account data (email, API
keys, settings, notes, blurbs, OIDC info) is never serialized here.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, col, select

from app.auth import hash_public_profile_token, require_user
from app.database import get_session
from app.models import PublicProfileAudience, PublicProfileLink, User
from app.schemas import (
    PublicProfileBook,
    PublicProfileResponse,
    PublicProfileSectionKey,
    PublicProfileUserInfo,
    StatisticsRange,
)
from app.services.public_profile import (
    BOOK_SECTIONS,
    build_public_books,
    filter_statistics,
    load_owner_books,
    parse_visibility_config,
)
from app.services.statistics import compute_statistics
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public-profiles", tags=["public-profile"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_optional_user(
    request: Request,
    x_api_key: str | None = Security(api_key_header),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: Session = Depends(get_session),
) -> User | None:
    """Resolve the viewer if a session or API key is present, else None.

    This is intentionally non-fatal: public links marked ``public`` must be
    viewable by anonymous visitors. Invalid credentials degrade to anonymous.
    """
    if not x_api_key and request.session.get("user_id") is None:
        return None
    try:
        return require_user(
            request=request,
            x_api_key=x_api_key,
            x_csrf_token=x_csrf_token,
            session=session,
        )
    except HTTPException:
        return None


@router.get("/{token}", response_model=PublicProfileResponse)
def get_public_profile(
    token: str,
    response: Response,
    viewer: User | None = Depends(get_optional_user),
    session: Session = Depends(get_session),
) -> PublicProfileResponse:
    """Return the whitelisted public profile for a share-link token.

    Invalid, expired, or revoked tokens all yield HTTP 404 so that link
    existence cannot be probed. Tokens restricted to logged-in users yield
    HTTP 401 for anonymous viewers.
    """
    _with_security_headers(response)
    link = session.exec(
        select(PublicProfileLink).where(
            PublicProfileLink.token_hash == hash_public_profile_token(token),
            col(PublicProfileLink.revoked_at).is_(None),
        )
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Public profile not found")

    now = utcnow()
    if link.expires_at is not None and link.expires_at < now:
        logger.debug("Public profile link expired: id=%s", link.id)
        raise HTTPException(status_code=404, detail="Public profile not found")

    if link.audience == PublicProfileAudience.authenticated and viewer is None:
        raise HTTPException(status_code=401, detail="Login required to view this profile")

    owner = session.get(User, link.user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Public profile not found")
    assert owner.id is not None

    config = parse_visibility_config(link.visibility_config_json)
    visible_sections = set(config.sections)

    books: list[PublicProfileBook] = []
    if visible_sections & set(BOOK_SECTIONS):
        books = build_public_books(session, load_owner_books(session, owner.id))

    statistics = None
    if PublicProfileSectionKey.statistics in visible_sections:
        full_stats = compute_statistics(
            session, owner.id, range_value=StatisticsRange.alltime
        )
        statistics = filter_statistics(full_stats, config.statistics)

    # The owner's name is only emitted when a section that renders it
    # (username or user_info) is visible, so it cannot leak through the
    # page title or share metadata otherwise.
    show_name = bool(
        visible_sections
        & {PublicProfileSectionKey.username, PublicProfileSectionKey.user_info}
    )

    return PublicProfileResponse(
        owner=PublicProfileUserInfo(
            firstname=owner.firstname if show_name else None,
            lastname=owner.lastname if show_name else None,
        ),
        audience=link.audience,
        language=link.language,
        expires_at=link.expires_at,
        visibility_config=config,
        books=books,
        statistics=statistics,
    )


def _with_security_headers(response: Response) -> Response:
    """Apply baseline security headers to the unauthenticated profile response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response