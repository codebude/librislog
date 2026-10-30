"""Tests for profile picture storage and the avatar APIs."""

import io
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.config import settings
from app.models import AvatarSource, User, UserImage
from app.services.avatar_storage import cleanup_orphan_avatars


def _png_bytes(size: tuple[int, int] = (640, 480)) -> bytes:
    image = Image.new("RGB", size, (40, 90, 140))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _upload(client: TestClient, body: bytes | None = None, content_type: str = "image/png"):
    return client.post(
        "/api/profile/avatar/upload",
        files={"file": ("avatar.png", body or _png_bytes(), content_type)},
    )


def test_avatar_options_default_to_animal(client: TestClient) -> None:
    response = client.get("/api/profile/avatar")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "animal"
    assert body["avatar_url"] is None
    assert body["has_uploaded_avatar"] is False
    assert body["has_oidc_avatar"] is False


def test_avatar_upload_switch_and_remove(client: TestClient) -> None:
    upload = _upload(client)
    assert upload.status_code == 200
    options = upload.json()
    assert options["source"] == "upload"
    assert options["has_uploaded_avatar"] is True
    assert options["avatar_url"]

    profile = client.get("/api/profile").json()
    assert profile["avatar_url"] == options["avatar_url"]

    served = client.get(options["avatar_url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["x-content-type-options"] == "nosniff"

    animal = client.patch("/api/profile/avatar", json={"source": "animal"})
    assert animal.status_code == 200
    assert animal.json()["source"] == "animal"
    assert animal.json()["avatar_url"] is None

    upload_again = client.patch("/api/profile/avatar", json={"source": "upload"})
    assert upload_again.status_code == 200
    assert upload_again.json()["source"] == "upload"

    removed = client.delete("/api/profile/avatar/upload")
    assert removed.status_code == 200
    assert removed.json()["source"] == "animal"
    assert removed.json()["has_uploaded_avatar"] is False


def test_avatar_source_requires_available_image(client: TestClient) -> None:
    assert client.patch("/api/profile/avatar", json={"source": "upload"}).status_code == 400
    assert client.patch("/api/profile/avatar", json={"source": "oidc"}).status_code == 400
    assert client.patch("/api/profile/avatar", json={"source": "bogus"}).status_code == 422


def test_avatar_upload_rejects_invalid_images(client: TestClient) -> None:
    assert _upload(client, b"not an image").status_code == 422
    assert _upload(client, _png_bytes(), content_type="image/svg+xml").status_code == 422


def test_cleanup_orphan_avatars(
    client: TestClient,
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "avatars_dir", str(tmp_path))

    referenced = tmp_path / "1__upload__referenced.webp"
    orphan = tmp_path / "1__upload__orphan.webp"
    recent = tmp_path / "1__upload__recent.webp"
    for path in (referenced, orphan, recent):
        path.write_bytes(b"data")

    # Make the orphan old enough to be eligible, and keep the recent file fresh.
    old = time.time() - 7200
    os.utime(orphan, (old, old))

    owner = session.exec(select(User)).first()
    assert owner is not None and owner.id is not None
    session.add(
        UserImage(
            user_id=owner.id,
            kind="avatar",
            variant="upload",
            filename=referenced.name,
            content_type="image/webp",
            byte_size=4,
        )
    )
    session.commit()

    deleted = cleanup_orphan_avatars(session, grace_minutes=60)
    assert deleted == 1
    assert orphan.exists() is False
    assert referenced.exists() is True
    assert recent.exists() is True


def test_public_profile_avatar_section(client: TestClient) -> None:
    uploaded = _upload(client)
    assert uploaded.status_code == 200

    created = client.post(
        "/api/profile/share-links",
        json={
            "name": "Avatar link",
            "audience": "public",
            "visibility_config": {
                "sections": ["username", "user_info", "avatar"],
                "statistics": [],
            },
        },
    )
    assert created.status_code == 201
    token = created.json()["token"]

    profile = client.get(f"/api/public-profiles/{token}", headers={"X-API-Key": ""})
    assert profile.status_code == 200
    assert "/avatar?v=" in profile.json()["owner"]["avatar_url"]

    avatar = client.get(f"/api/public-profiles/{token}/avatar", headers={"X-API-Key": ""})
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/webp"

    link_id = created.json()["link"]["id"]
    updated = client.patch(
        f"/api/profile/share-links/{link_id}",
        json={
            "visibility_config": {
                "sections": ["username", "user_info"],
                "statistics": [],
            }
        },
    )
    assert updated.status_code == 200

    hidden_profile = client.get(f"/api/public-profiles/{token}", headers={"X-API-Key": ""})
    assert hidden_profile.json()["owner"]["avatar_url"] is None
    hidden_avatar = client.get(f"/api/public-profiles/{token}/avatar", headers={"X-API-Key": ""})
    assert hidden_avatar.status_code == 404


def test_oidc_picture_url_validation() -> None:
    from app.services.avatar_storage import is_safe_oidc_picture_url

    assert is_safe_oidc_picture_url("http://example.com/avatar.png") is False
    assert is_safe_oidc_picture_url("ftp://example.com/avatar.png") is False
    assert is_safe_oidc_picture_url("https://user:pass@example.com/avatar.png") is False
    assert is_safe_oidc_picture_url("https://example.com/avatar.png#fragment") is False
    assert is_safe_oidc_picture_url("https://example.com/" + "a" * 3000) is False
    assert is_safe_oidc_picture_url("https://127.0.0.1/avatar.png") is False
    assert is_safe_oidc_picture_url("https://localhost/avatar.png") is False


def test_delete_all_user_avatar_images(
    client: TestClient,
    session: Session,
) -> None:
    from app.services.avatar_storage import delete_avatar_file
    from app.services.avatar import delete_all_user_avatar_images

    uploaded = _upload(client)
    assert uploaded.status_code == 200
    me = client.get("/api/auth/me").json()
    user_id = me["id"]

    image = session.exec(
        select(UserImage).where(UserImage.user_id == user_id, UserImage.variant == "upload")
    ).first()
    assert image is not None
    filename = image.filename
    assert filename is not None

    removed = delete_all_user_avatar_images(session, user_id)
    session.commit()
    assert removed == [filename]
    assert session.exec(select(UserImage).where(UserImage.user_id == user_id)).first() is None
    delete_avatar_file(filename, settings.avatars_dir)


def test_load_avatar_urls_returns_one_url_per_user(
    client: TestClient,
    session: Session,
) -> None:
    from app.services.avatar import load_avatar_urls

    assert _upload(client).status_code == 200
    me = client.get("/api/auth/me").json()
    user = session.get(User, me["id"])
    assert user is not None
    urls = load_avatar_urls(session, [user])
    assert set(urls) == {user.id}
    assert urls[user.id] is not None


def test_upload_size_limit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "avatar_max_upload_mb", 0)
    response = _upload(client)
    assert response.status_code == 413


def test_authenticated_only_public_avatar_requires_login(client: TestClient) -> None:
    assert _upload(client).status_code == 200
    created = client.post(
        "/api/profile/share-links",
        json={
            "name": "Private avatar",
            "audience": "authenticated",
            "visibility_config": {"sections": ["avatar"], "statistics": []},
        },
    )
    assert created.status_code == 201
    token = created.json()["token"]

    anonymous = client.get(
        f"/api/public-profiles/{token}/avatar",
        headers={"X-API-Key": ""},
    )
    assert anonymous.status_code == 401


def test_oidc_unlink_falls_back_to_upload(
    client: TestClient,
    session: Session,
) -> None:
    from app.models import OidcLink

    assert _upload(client).status_code == 200
    me = client.get("/api/auth/me").json()
    user = session.get(User, me["id"])
    assert user is not None and user.id is not None
    user.avatar_source = AvatarSource.oidc
    session.add(
        UserImage(
            user_id=user.id,
            kind="avatar",
            variant="oidc",
            filename="missing-oidc.webp",
            content_type="image/webp",
        )
    )
    session.add(
        OidcLink(user_id=user.id, provider_id="test", oidc_sub="unlink-sub")
    )
    session.commit()

    response = client.delete("/api/oidc/unlink")
    assert response.status_code == 204

    session.refresh(user)
    assert user.avatar_source == AvatarSource.upload


def test_authenticated_avatar_endpoint_denies_other_users(
    client: TestClient,
    create_user_with_key,
) -> None:
    assert _upload(client).status_code == 200
    me = client.get("/api/auth/me").json()
    _, other_key = create_user_with_key(email="other@example.com")

    response = client.get(
        f"/api/users/{me['id']}/avatar",
        headers={"X-API-Key": other_key},
    )
    assert response.status_code == 404


def test_authenticated_only_public_avatar_serves_logged_in_viewer(client: TestClient) -> None:
    assert _upload(client).status_code == 200
    created = client.post(
        "/api/profile/share-links",
        json={
            "name": "Private avatar viewer",
            "audience": "authenticated",
            "visibility_config": {"sections": ["avatar"], "statistics": []},
        },
    )
    assert created.status_code == 201
    token = created.json()["token"]

    response = client.get(f"/api/public-profiles/{token}/avatar")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private")


def test_oidc_picture_url_allows_the_provider_host() -> None:
    from app.services.avatar_storage import is_safe_oidc_picture_url

    assert (
        is_safe_oidc_picture_url(
            "https://127.0.0.1/profile-picture.png",
            trusted_private_host="127.0.0.1",
        )
        is True
    )
    assert (
        is_safe_oidc_picture_url(
            "https://10.0.0.5/profile-picture.png",
            trusted_private_host="10.0.0.5",
        )
        is True
    )
    assert is_safe_oidc_picture_url("https://127.0.0.1/profile-picture.png") is False
    assert (
        is_safe_oidc_picture_url(
            "https://10.0.0.5/profile-picture.png",
            trusted_private_host="id.example.com",
        )
        is False
    )
