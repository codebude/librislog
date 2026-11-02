"""Database and domain helpers for user avatar images."""

from typing import Iterable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import AvatarSource, OidcLink, User, UserImage
from app.schemas import AvatarOptionsRead, UserRead
from app.services.avatar_storage import StoredAvatar, resolve_avatar_path
from app.time_utils import utcnow

KIND_AVATAR = "avatar"
VARIANT_UPLOAD = "upload"
VARIANT_OIDC = "oidc"


def get_user_image(
    session: Session,
    user_id: int,
    variant: str,
    kind: str = KIND_AVATAR,
) -> UserImage | None:
    """Return the user's image row for *kind* and *variant*, if any."""
    return session.exec(
        select(UserImage).where(
            UserImage.user_id == user_id,
            UserImage.kind == kind,
            UserImage.variant == variant,
        )
    ).first()


def selected_avatar_image(session: Session, user: User) -> UserImage | None:
    """Return the image row selected by ``user.avatar_source``."""
    if user.id is None or user.avatar_source == AvatarSource.animal:
        return None
    variant = VARIANT_OIDC if user.avatar_source == AvatarSource.oidc else VARIANT_UPLOAD
    return get_user_image(session, user.id, variant)


def image_has_file(image: UserImage | None, avatars_dir: str) -> bool:
    if image is None or not image.filename:
        return False
    path = resolve_avatar_path(image.filename, avatars_dir)
    return path is not None and path.is_file()


def _apply_avatar_fields(
    image: UserImage,
    stored: StoredAvatar | None,
    external_url: str | None,
) -> UserImage:
    if stored is not None:
        image.filename = stored.filename
        image.content_type = stored.content_type
        image.byte_size = stored.byte_size
    image.external_url = external_url
    image.updated_at = utcnow()
    return image


def upsert_avatar_image(
    session: Session,
    user_id: int,
    variant: str,
    stored: StoredAvatar | None = None,
    external_url: str | None = None,
    kind: str = KIND_AVATAR,
) -> UserImage:
    """Create or update the avatar row for *variant*.

    ``stored`` may be ``None`` when only the provider URL is known and the
    download failed or was not requested. The previous file is not deleted
    here. Callers should delete the old filename after the transaction
    commits, or leave it for the periodic orphan cleanup. This keeps a
    rollback from leaving the user with a row that points to a missing file.
    """
    for attempt in range(2):
        try:
            # A savepoint keeps a concurrent-duplicate retry from rolling back
            # unrelated pending work (for example a new OidcLink row).
            with session.begin_nested():
                image = get_user_image(session, user_id, variant, kind=kind)
                if image is None:
                    image = UserImage(
                        user_id=user_id,
                        kind=kind,
                        variant=variant,
                        external_url=external_url,
                    )
                    session.add(image)
                _apply_avatar_fields(image, stored, external_url)
                session.add(image)
                session.flush()
            return image
        except IntegrityError:
            # Two concurrent logins or uploads may both try to insert the same
            # (user_id, kind, variant). The conflicting row is now visible, so
            # retry once and update it instead.
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


def delete_avatar_image(
    session: Session,
    user_id: int,
    variant: str,
    kind: str = KIND_AVATAR,
) -> str | None:
    """Delete an avatar row and return its filename for post-commit cleanup."""
    image = get_user_image(session, user_id, variant, kind=kind)
    if image is None:
        return None
    filename = image.filename
    session.delete(image)
    session.flush()
    return filename


def delete_all_user_avatar_images(
    session: Session,
    user_id: int,
    kind: str = KIND_AVATAR,
) -> list[str]:
    """Delete every avatar row for *user_id* and return filenames to clean up."""
    images = session.exec(
        select(UserImage).where(
            UserImage.user_id == user_id,
            UserImage.kind == kind,
        )
    ).all()
    filenames: list[str] = []
    for image in images:
        if image.filename:
            filenames.append(image.filename)
        session.delete(image)
    session.flush()
    return filenames


def avatar_version(image: UserImage | None) -> int | None:
    """Return a cache-busting version for *image*."""
    if image is None or image.updated_at is None:
        return None
    return int(image.updated_at.timestamp() * 1000)


def user_avatar_url(user_id: int, image: UserImage | None) -> str | None:
    """Return the authenticated avatar URL for *user_id*, or None."""
    if image is None or not image.filename:
        return None
    version = avatar_version(image)
    suffix = f"?v={version}" if version is not None else ""
    return f"/api/users/{user_id}/avatar{suffix}"


def public_avatar_url(token: str, image: UserImage | None) -> str | None:
    """Return the public avatar URL for a share-link *token*, or None."""
    if image is None or not image.filename:
        return None
    version = avatar_version(image)
    suffix = f"?v={version}" if version is not None else ""
    return f"/api/public-profiles/{token}/avatar{suffix}"


def build_user_read(session: Session, user: User) -> UserRead:
    """Build a ``UserRead`` including the effective avatar URL."""
    image = selected_avatar_image(session, user)
    return UserRead(
        id=user.id,
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        avatar_url=user_avatar_url(user.id, image) if user.id is not None else None,
    )


def load_avatar_urls(
    session: Session,
    users: Iterable[User],
) -> dict[int, str | None]:
    """Return one avatar URL per user without querying once per user."""
    user_list = [user for user in users if user.id is not None]
    if not user_list:
        return {}

    user_ids = [user.id for user in user_list]
    images = session.exec(
        select(UserImage).where(
            UserImage.user_id.in_(user_ids),
            UserImage.kind == KIND_AVATAR,
        )
    ).all()
    by_user_variant = {(image.user_id, image.variant): image for image in images}

    urls: dict[int, str | None] = {}
    for user in user_list:
        assert user.id is not None
        if user.avatar_source == AvatarSource.animal:
            urls[user.id] = None
            continue
        variant = VARIANT_OIDC if user.avatar_source == AvatarSource.oidc else VARIANT_UPLOAD
        urls[user.id] = user_avatar_url(user.id, by_user_variant.get((user.id, variant)))
    return urls


def build_avatar_options(session: Session, user: User, avatars_dir: str) -> AvatarOptionsRead:
    """Build the profile avatar card state for *user*."""
    assert user.id is not None
    upload = get_user_image(session, user.id, VARIANT_UPLOAD)
    oidc = get_user_image(session, user.id, VARIANT_OIDC)
    oidc_link = session.exec(
        select(OidcLink).where(OidcLink.user_id == user.id)
    ).first()
    selected = selected_avatar_image(session, user)
    selected_has_file = image_has_file(selected, avatars_dir)
    return AvatarOptionsRead(
        source=user.avatar_source,
        avatar_url=user_avatar_url(user.id, selected) if selected_has_file else None,
        has_uploaded_avatar=image_has_file(upload, avatars_dir),
        has_oidc_avatar=image_has_file(oidc, avatars_dir),
        oidc_linked=oidc_link is not None,
    )
