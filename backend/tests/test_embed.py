"""Tests for embed token lifecycle and the embed HTML widget endpoint."""

import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlmodel import Session, select

from app.auth import generate_embed_token, hash_embed_token
from app.models import Book, EmbedToken, UserRole
from app.time_utils import utcnow

# ── Helpers ──────────────────────────────────────────────────────────────


def _create_token(
    session: Session,
    user_id: int,
    *,
    name: str = "Test Token",
    allowed_origins: str | None = None,
    expires_at: datetime | None = None,
) -> str:
    plain = generate_embed_token()
    token = EmbedToken(
        user_id=user_id,
        name=name,
        token_prefix=plain[:12],
        token_hash=hash_embed_token(plain),
        allowed_origins=allowed_origins,
        expires_at=expires_at,
    )
    session.add(token)
    session.commit()
    return plain


# ── Profile CRUD Tests ───────────────────────────────────────────────────


class TestListEmbedTokens:
    def test_lists_own_tokens(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get("/api/profile/embed-tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["token_prefix"] == plain[:12]

    def test_does_not_list_revoked_tokens(
        self, client: TestClient, session: Session, create_user_with_key: Callable[..., Any]
    ) -> None:
        user, key = create_user_with_key(email="embed_list@example.com")
        client.headers["X-API-Key"] = key
        plain = _create_token(session, user.id)
        # Revoke it
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None
        token.revoked_at = utcnow()
        session.add(token)
        session.commit()
        resp = client.get("/api/profile/embed-tokens")
        assert resp.status_code == 200
        assert all(t["token_prefix"] != plain[:12] for t in resp.json())

    def test_other_user_cannot_see_tokens(
        self, client: TestClient, session: Session, create_user_with_key: Callable[..., Any]
    ) -> None:
        user, key = create_user_with_key(email="other_embed@example.com")
        client.headers["X-API-Key"] = key
        _create_token(session, user_id=user.id, name="Secret")
        resp = client.get("/api/profile/embed-tokens")
        assert resp.status_code == 200
        assert len(resp.json()) == 1  # only own tokens


class TestCreateEmbedToken:
    def test_creates_token(self, client: TestClient) -> None:
        resp = client.post(
            "/api/profile/embed-tokens",
            json={"name": "Homarr Widget"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["token"].startswith("le_")
        assert data["embed_token"]["name"] == "Homarr Widget"
        assert data["embed_token"]["token_prefix"] == data["token"][:12]

    def test_with_allowed_origins(self, client: TestClient) -> None:
        resp = client.post(
            "/api/profile/embed-tokens",
            json={
                "name": "With Origins",
                "allowed_origins": "https://homarr.local,https://dashy.local",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["embed_token"]["allowed_origins"] == "https://homarr.local,https://dashy.local"

    def test_with_expiry(self, client: TestClient) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        resp = client.post(
            "/api/profile/embed-tokens",
            json={"name": "Expiring", "expires_at": expires},
        )
        assert resp.status_code == 201


class TestUpdateEmbedToken:
    def test_updates_name_and_origins(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None
        resp = client.patch(
            f"/api/profile/embed-tokens/{token.id}",
            json={"name": "Renamed", "allowed_origins": "https://example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"
        assert resp.json()["allowed_origins"] == "https://example.com"

    def test_not_found_for_other_user(
        self, client: TestClient, session: Session, create_user_with_key: Callable[..., Any]
    ) -> None:
        user, key = create_user_with_key(email="other_update@example.com")
        client.headers["X-API-Key"] = key
        resp = client.patch("/api/profile/embed-tokens/99999", json={"name": "Nope"})
        assert resp.status_code == 404


class TestRotateEmbedToken:
    def test_rotate_returns_new_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1, name="Rotate Me")
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None
        old_id = token.id
        resp = client.post(f"/api/profile/embed-tokens/{old_id}/rotate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"].startswith("le_")
        assert data["token"] != plain
        assert data["embed_token"]["name"] == "Rotate Me"
        assert data["embed_token"]["id"] != old_id
        # Old token should be revoked
        session.expire_all()
        old = session.get(EmbedToken, old_id)
        assert old is not None
        assert old.revoked_at is not None

    def test_cannot_rotate_expired_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(
            session,
            user_id=1,
            name="Expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None

        resp = client.post(f"/api/profile/embed-tokens/{token.id}/rotate")
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Expired embed tokens cannot be rotated"


class TestDeleteEmbedToken:
    def test_revokes_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None
        resp = client.delete(f"/api/profile/embed-tokens/{token.id}")
        assert resp.status_code == 204
        session.expire_all()
        deleted = session.get(EmbedToken, token.id)
        assert deleted is not None
        assert deleted.revoked_at is not None

    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/profile/embed-tokens/99999")
        assert resp.status_code == 404


# ── Embed Widget Endpoint Tests ──────────────────────────────────────────


class TestEmbedStatsEndpoint:
    def test_returns_html_with_valid_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "<!DOCTYPE html>" in resp.text
        assert "Books" in resp.text

    def test_401_for_invalid_token(self, client: TestClient) -> None:
        resp = client.get("/embed/v1/stats?token=le_invalid")
        assert resp.status_code == 401

    def test_401_for_revoked_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        token = session.exec(
            select(EmbedToken).where(EmbedToken.token_hash == hash_embed_token(plain))
        ).first()
        assert token is not None
        token.revoked_at = utcnow()
        session.add(token)
        session.commit()
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 401

    def test_401_for_expired_token(self, client: TestClient, session: Session) -> None:
        plain = _create_token(
            session, user_id=1,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 401

    def test_shows_stats_for_user(self, client: TestClient, session: Session) -> None:
        for i in range(3):
            session.add(Book(title=f"Book {i}", author="Author", page_count=200, user_id=1, reading_status="read"))
        session.commit()

        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 200
        assert "3" in resp.text

    def test_user_isolation(self, client: TestClient, session: Session) -> None:
        for i in range(5):
            session.add(Book(title=f"U1 Book {i}", author="Author", page_count=100, user_id=1, reading_status="want_to_read"))
        session.commit()

        from app.auth import generate_api_key, get_api_key_prefix, get_password_hash, hash_api_key, encrypt_api_key
        from app.models import ApiKey, User, UserSettings

        user2 = User(firstname="User", lastname="Two", email="u2@example.com",
                     role=UserRole.user, hashed_password=get_password_hash("secret"))
        session.add(user2)
        session.commit()
        session.refresh(user2)
        assert user2.id is not None
        session.add(UserSettings(user_id=user2.id, language="en"))
        key2 = generate_api_key()
        session.add(ApiKey(user_id=user2.id, key_prefix=get_api_key_prefix(key2),
                           key_hash=hash_api_key(key2), key_encrypted=encrypt_api_key(key2),
                           description="Key"))
        session.commit()
        plain = _create_token(session, user2.id)
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 200
        text = resp.text
        books_match = re.search(r'<div[^>]*>\s*0\s*</div>', text)
        assert books_match, f"Expected '0' somewhere in stats, got: {text[:500]}"

    def test_403_for_disallowed_origin(self, client: TestClient, session: Session) -> None:
        plain = _create_token(
            session, user_id=1,
            allowed_origins="https://allowed.example.com",
        )
        resp = client.get(
            f"/embed/v1/stats?token={plain}",
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.status_code == 403

    def test_wildcard_origin_allows_any(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)  # allowed_origins=None = wildcard
        resp = client.get(
            f"/embed/v1/stats?token={plain}",
            headers={"Origin": "https://any-dashboard.local"},
        )
        assert resp.status_code == 200

    def test_style_params_are_applied(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(
            f"/embed/v1/stats?token={plain}&theme=dark&accent=%23ff0000&radius=lg&density=compact"
        )
        assert resp.status_code == 200
        assert "#ff0000" in resp.text

    def test_missing_token_returns_422(self, client: TestClient) -> None:
        resp = client.get("/embed/v1/stats")
        assert resp.status_code == 422

    def test_show_param_filters_stats(self, client: TestClient, session: Session) -> None:
        for i in range(3):
            session.add(Book(title=f"Book {i}", author="Author", page_count=200, user_id=1, reading_status="read"))
        session.commit()
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&show=books,pages")
        assert resp.status_code == 200
        assert "Books" in resp.text
        assert "Pages" in resp.text
        assert "Reading" not in resp.text

    def test_show_param_invalid_key_returns_422(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&show=invalid_key")
        assert resp.status_code == 422

    def test_lang_param_sets_html_lang_and_translates_labels(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&lang=de")
        assert resp.status_code == 200
        assert 'lang="de"' in resp.text
        assert "Gelesen" in resp.text
        assert "Books" not in resp.text

    def test_lang_param_with_region_falls_back_to_base_language(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&lang=fr-CA")
        assert resp.status_code == 200
        assert 'lang="fr-CA"' in resp.text
        assert "Livres" in resp.text

    def test_font_scale_param(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&font_scale=1.5")
        assert resp.status_code == 200
        assert "21.0px" in resp.text

    def test_font_scale_out_of_range_returns_422(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&font_scale=5.0")
        assert resp.status_code == 422

    def test_layout_list(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&layout=list")
        assert resp.status_code == 200
        assert "flex-direction:column" in resp.text

    def test_layout_invalid_returns_422(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}&layout=bad")
        assert resp.status_code == 422

    def test_security_headers(self, client: TestClient, session: Session) -> None:
        plain = _create_token(session, user_id=1)
        resp = client.get(f"/embed/v1/stats?token={plain}")
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "private, max-age=60"
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("referrer-policy") == "no-referrer"
        assert resp.headers.get("content-security-policy") == "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors *"


# ── Direct unit tests for uncovered embed branches ───────────────────────


def _make_fake_path_class(tmp_path: Path):
    """Return a minimal Path stand-in that redirects embed i18n lookups to tmp_path."""

    class FakePath:
        def __init__(self, *parts: str):
            self._parts = parts
            if not parts or parts == ("i18n",):
                self._path = tmp_path
            else:
                self._path = tmp_path.joinpath(*parts)

        def resolve(self):
            return self

        @property
        def parent(self):
            return FakePath()

        def __truediv__(self, other: str):
            if other == "i18n":
                return FakePath()
            return FakePath(other)

        def glob(self, pattern: str):
            return [FakePath(p.name) for p in sorted(tmp_path.glob(pattern))]

        @property
        def stem(self):
            return self._path.stem

        def open(self, *args, **kwargs):
            return self._path.open(*args, **kwargs)

        def __str__(self):
            return str(self._path)

        @property
        def name(self):
            return self._path.name

    return FakePath


def test_load_stat_labels_skips_invalid_stats(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.routers import embed as embed_module

    (tmp_path / "de.json").write_text(json.dumps({"embed": {"stats": "not-a-dict"}}))
    (tmp_path / "en.json").write_text(
        json.dumps(
            {
                "embed": {
                    "stats": {
                        "books": "Books",
                        "reading": "Reading",
                        "read": "Read",
                        "to_read": "To Read",
                        "pages": "Pages",
                        "avg_pages": "Avg/Book",
                    }
                }
            }
        )
    )
    monkeypatch.setattr(embed_module, "Path", _make_fake_path_class(tmp_path))
    labels = embed_module._load_stat_labels()
    assert "en" in labels
    assert "de" not in labels


def test_load_stat_labels_missing_required_key(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.routers import embed as embed_module

    (tmp_path / "en.json").write_text(json.dumps({"embed": {"stats": {"books": "Books"}}}))
    monkeypatch.setattr(embed_module, "Path", _make_fake_path_class(tmp_path))
    with pytest.raises(RuntimeError, match="missing embed.stats keys"):
        embed_module._load_stat_labels()


def test_load_stat_labels_missing_english(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from app.routers import embed as embed_module

    (tmp_path / "de.json").write_text(
        json.dumps(
            {
                "embed": {
                    "stats": {
                        "books": "B\u00fccher",
                        "reading": "Lesen",
                        "read": "Gelesen",
                        "to_read": "Zu lesen",
                        "pages": "Seiten",
                        "avg_pages": "\u00d8/Buch",
                    }
                }
            }
        )
    )
    monkeypatch.setattr(embed_module, "Path", _make_fake_path_class(tmp_path))
    with pytest.raises(RuntimeError, match="expected at least en.json"):
        embed_module._load_stat_labels()


def test_verify_embed_token_missing_scope(client: TestClient, session: Session) -> None:
    from app.routers.embed import _verify_embed_token

    plain = generate_embed_token()
    token = EmbedToken(
        user_id=1,
        name="No Scope",
        token_prefix=plain[:12],
        token_hash=hash_embed_token(plain),
        scopes="other:scope",
    )
    session.add(token)
    session.commit()

    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as exc_info:
        _verify_embed_token(plain, session, request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token lacks required scope"


def test_verify_embed_token_empty_origin_allowed(client: TestClient, session: Session) -> None:
    from app.routers.embed import _verify_embed_token

    plain = _create_token(session, user_id=1, allowed_origins="https://example.com")
    request = Request({"type": "http", "headers": []})
    user = _verify_embed_token(plain, session, request)
    assert user.email == "test@example.com"


def test_verify_embed_token_user_not_found(session: Session) -> None:
    from app.auth import get_password_hash
    from app.models import User
    from app.routers.embed import _verify_embed_token

    user = User(
        firstname="Orphan",
        lastname="Token",
        email="orphan@example.com",
        role=UserRole.user,
        hashed_password=get_password_hash("secret"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    plain = generate_embed_token()
    token = EmbedToken(
        user_id=user.id,
        name="Orphan",
        token_prefix=plain[:12],
        token_hash=hash_embed_token(plain),
    )
    session.add(token)
    session.commit()

    session.delete(user)
    session.commit()

    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as exc_info:
        _verify_embed_token(plain, session, request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token user not found"


def test_render_stats_html_zero_items_grid() -> None:
    from app.routers.embed import _render_stats_html

    html = _render_stats_html(
        {},
        theme="light",
        accent="#000000",
        radius="md",
        density="normal",
        hide_labels=False,
        lang="en",
        font_scale=1.0,
        layout="grid",
        show={"not_a_stat"},
    )
    assert "grid-template-columns:repeat(1,1fr)" in html
