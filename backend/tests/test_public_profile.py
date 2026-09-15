"""Tests for public profile share links — management CRUD and the public endpoint."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.auth import hash_public_profile_token
from app.models import AcquisitionStatus, Book, PublicProfileLink, ReadingStatus
from app.time_utils import utcnow


def _create_share_link(client: Any, **overrides: Any) -> dict[str, Any]:
    """Create a share link via the API and return the JSON response."""
    payload = {
        "name": "My Profile",
        "visibility_config": {
            "sections": ["username", "currently_reading", "statistics"],
            "statistics": ["total_books", "status_distribution"],
        },
        **overrides,
    }
    resp = client.post("/api/profile/share-links", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _public_profile(client: Any, token: str) -> Any:
    """Call the public profile endpoint with the raw token."""
    return client.get(f"/api/public-profiles/{token}")


def _create_book(client: Any, title: str = "Book", **overrides: Any) -> dict[str, Any]:
    """Create a book via the API and return the JSON response."""
    payload = {"title": title, "authors": ["Test Author"], "page_count": 100, **overrides}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_share_link_language_roundtrip(client: Any) -> None:
    """Language is set on create, appears in list, and survives an update."""
    data = _create_share_link(client, language="de")
    assert data["link"]["language"] == "de"

    listed = client.get("/api/profile/share-links")
    assert listed.json()[0]["language"] == "de"

    link_id = data["link"]["id"]
    resp = client.patch(f"/api/profile/share-links/{link_id}", json={"language": "fr"})
    assert resp.status_code == 200
    assert resp.json()["language"] == "fr"

    public = _public_profile(client, data["token"])
    assert public.status_code == 200
    assert public.json()["language"] == "fr"


def test_create_share_link_returns_token_once(client: Any) -> None:
    data = _create_share_link(client)
    assert data["token"].startswith("lp_")
    assert data["link"]["name"] == "My Profile"
    assert data["link"]["token_prefix"] == data["token"][:12]
    assert data["link"]["visibility_config"]["sections"] == [
        "username",
        "currently_reading",
        "statistics",
    ]

    # Listing must not expose the full token.
    listed = client.get("/api/profile/share-links")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert "token" not in items[0]
    assert items[0]["token_prefix"] == data["token"][:12]


def test_list_share_links_isolated(client: Any, create_user_with_key: Any) -> None:
    _create_share_link(client)
    created = client.get("/api/profile/share-links").json()
    assert len(created) == 1
    link_id = created[0]["id"]

    user_b, key_b = create_user_with_key(email="other@example.com")

    # User B's key cannot see A's links.
    assert client.get(
        "/api/profile/share-links", headers={"X-API-Key": key_b}
    ).json() == []

    # User B's key cannot modify or delete A's links.
    assert (
        client.delete(
            f"/api/profile/share-links/{link_id}", headers={"X-API-Key": key_b}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/profile/share-links/{link_id}",
            headers={"X-API-Key": key_b},
            json={"name": "Hijacked"},
        ).status_code
        == 404
    )
    assert client.get("/api/profile/share-links").json()[0]["id"] == link_id


def _public_profile_with_client(client: Any, token: str, x_api_key: str | None = None) -> Any:
    """Call public endpoint with an explicit API key header.

    The client fixture always attaches the owner's key; when *x_api_key* is
    None that header is removed so the request is truly anonymous.
    """
    if x_api_key is None:
        client.headers.pop("X-API-Key", None)
        return client.get(f"/api/public-profiles/{token}")
    return client.get(f"/api/public-profiles/{token}", headers={"X-API-Key": x_api_key})


def test_public_profile_success(client: Any) -> None:
    _create_book(client, title="Currently Reading", reading_status="currently_reading")
    _create_book(client, title="Finished", reading_status="read", date_finished=utcnow().isoformat())

    data = _create_share_link(client)
    token = data["token"]

    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner"] == {"firstname": "Test", "lastname": "User"}
    assert body["audience"] == "public"
    assert body["visibility_config"]["sections"] == ["username", "currently_reading", "statistics"]
    assert len(body["books"]) == 2
    assert {b["title"] for b in body["books"]} == {"Currently Reading", "Finished"}
    assert "authors" in body["books"][0]
    assert body["books"][0]["authors"] == ["Test Author"]
    # Statistics are filtered to selected keys only.
    assert set(body["statistics"].keys()) == {"total_books", "status_distribution"}
    assert body["statistics"]["total_books"] == 2
    assert body["statistics"]["status_distribution"]["currently_reading"] == 1
    assert body["statistics"]["status_distribution"]["read"] == 1


def test_public_profile_invalid_token_returns_404(client: Any) -> None:
    resp = _public_profile_with_client(client, "lp_does-not-exist", x_api_key=None)
    assert resp.status_code == 404


def test_public_profile_expired_returns_404(client: Any, session: Session) -> None:
    data = _create_share_link(
        client,
        expires_at=(utcnow() + timedelta(days=1)).isoformat(),
    )
    token = data["token"]
    link_id = data["link"]["id"]

    # Back-date the expiry in the DB (the API rejects past dates on write).
    link = session.get(PublicProfileLink, link_id)
    assert link is not None
    link.expires_at = utcnow() - timedelta(days=1)
    session.add(link)
    session.commit()

    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 404


def test_public_profile_revoked_returns_404(client: Any) -> None:
    data = _create_share_link(client)
    token = data["token"]
    link_id = data["link"]["id"]

    resp = client.delete(f"/api/profile/share-links/{link_id}")
    assert resp.status_code == 204

    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 404


def test_public_profile_authenticated_audience_blocks_anonymous(client: Any) -> None:
    data = _create_share_link(client, audience="authenticated")
    token = data["token"]

    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 401


def test_public_profile_audience_public_allows_anonymous_with_invalid_key(client: Any) -> None:
    data = _create_share_link(client, audience="public")
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key="lk_invalid-key")
    assert resp.status_code == 200


def test_public_profile_authenticated_audience_allows_logged_in(
    client: Any,
    create_user_with_key: Any,
) -> None:
    data = _create_share_link(client, audience="authenticated")
    token = data["token"]

    user_b, key_b = create_user_with_key(email="viewer@example.com")

    assert key_b  # viewer is a different logged-in user
    resp = _public_profile_with_client(client, token, x_api_key=key_b)
    assert resp.status_code == 200
    assert resp.json()["owner"]["firstname"] == "Test"


def test_public_profile_update_share_link(client: Any) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]

    resp = client.patch(
        f"/api/profile/share-links/{link_id}",
        json={
            "name": "Renamed",
            "audience": "authenticated",
            "visibility_config": {"sections": ["full_library"], "statistics": []},
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["audience"] == "authenticated"
    assert body["visibility_config"]["sections"] == ["full_library"]


def test_public_profile_delete_revokes(client: Any) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]
    resp = client.delete(f"/api/profile/share-links/{link_id}")
    assert resp.status_code == 204

    listed = client.get("/api/profile/share-links")
    assert listed.json() == []


def test_public_profile_cross_user_isolation(client: Any, session: Session, create_user_with_key: Any) -> None:
    """A public profile only ever exposes the owner's books."""
    _create_book(client, title="Owner Book")
    data = _create_share_link(client)
    token = data["token"]

    user_b, _ = create_user_with_key(email="other@example.com")
    # Insert a book owned by the other user directly into the DB.
    session.add(
        Book(
            user_id=user_b.id,
            title="Other User's Book",
            page_count=50,
            reading_status=ReadingStatus.want_to_read,
            acquisition_status=AcquisitionStatus.owned,
        )
    )
    session.commit()

    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    assert [b["title"] for b in resp.json()["books"]] == ["Owner Book"]


def test_public_profile_never_returns_sensitive_fields(client: Any) -> None:
    _create_book(client, title="Read", reading_status="read")
    data = _create_share_link(
        client,
        visibility_config={
            "sections": ["username", "user_info", "full_library", "currently_reading", "last_read", "reading_timeline", "statistics"],
            "statistics": [],
        },
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    raw = resp.json()

    body_text = str(raw)
    assert "email" not in body_text
    assert "@" not in body_text
    assert "password" not in body_text
    assert "api_key" not in body_text
    assert "notes" not in body_text
    assert "blurb" not in body_text
    assert "settings" not in body_text

    book = raw["books"][0]
    assert "notes" not in book
    assert "blurb" not in book


def test_public_profile_respects_visibility_config_for_books(client: Any) -> None:
    """When no book section is enabled, the books payload is empty."""
    _create_book(client, title="A Book")
    data = _create_share_link(
        client,
        visibility_config={"sections": ["username"], "statistics": []},
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["books"] == []
    assert body["statistics"] is None


def test_public_profile_did_not_finish_books_still_whitelisted(client: Any) -> None:
    _create_book(client, title="DNF", reading_status="did_not_finish")
    data = _create_share_link(
        client,
        visibility_config={"sections": ["full_library"], "statistics": []},
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    assert [b["title"] for b in resp.json()["books"]] == ["DNF"]
    assert resp.json()["books"][0]["reading_status"] == "did_not_finish"


def test_public_profile_statistics_only_selected_keys(client: Any) -> None:
    _create_book(client, title="Read", reading_status="read", rating=5)
    data = _create_share_link(
        client,
        visibility_config={
            "sections": ["statistics"],
            "statistics": ["average_rating", "total_authors"],
        },
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    stats = resp.json()["statistics"]
    assert set(stats.keys()) == {"average_rating", "total_authors"}
    assert stats["average_rating"] == 5.0


def test_public_profile_statistics_include_companion_counts(client: Any) -> None:
    """Selected summary stats bring along the *_count fields that describe them."""
    _create_book(
        client,
        title="Read",
        reading_status="read",
        language="de",
        date_finished=utcnow().isoformat(),
    )
    data = _create_share_link(
        client,
        visibility_config={
            "sections": ["statistics"],
            "statistics": [
                "busiest_month",
                "most_popular_language",
                "total_books",
            ],
        },
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    stats = resp.json()["statistics"]
    assert set(stats.keys()) == {
        "total_books",
        "busiest_month",
        "busiest_month_count",
        "most_popular_language",
        "most_popular_language_count",
    }
    assert stats["busiest_month_count"] is not None
    assert stats["most_popular_language_count"] is not None


def test_public_profile_redacts_owner_name_when_hidden(client: Any) -> None:
    """Names are never emitted unless a section renders them."""
    data = _create_share_link(
        client,
        visibility_config={"sections": ["full_library"], "statistics": []},
    )
    token = data["token"]
    resp = _public_profile_with_client(client, token, x_api_key=None)
    assert resp.status_code == 200
    owner = resp.json()["owner"]
    assert owner == {"firstname": None, "lastname": None}


def test_public_profile_sets_security_headers(client: Any) -> None:
    data = _create_share_link(client)
    token = data["token"]
    resp = client.get(f"/api/public-profiles/{token}")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_public_profile_rejects_past_expiry_on_create(client: Any) -> None:
    resp = client.post(
        "/api/profile/share-links",
        json={
            "name": "Expired",
            "expires_at": (utcnow() - timedelta(days=1)).isoformat(),
        },
    )
    assert resp.status_code == 422
    assert "future" in resp.json()["detail"]


def test_public_profile_rejects_past_expiry_on_update(client: Any) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]
    resp = client.patch(
        f"/api/profile/share-links/{link_id}",
        json={"expires_at": (utcnow() - timedelta(minutes=5)).isoformat()},
    )
    assert resp.status_code == 422
    assert "future" in resp.json()["detail"]

    # Clearing the expiry is still allowed.
    resp = client.patch(
        f"/api/profile/share-links/{link_id}",
        json={"expires_at": None},
    )
    assert resp.status_code == 200
    assert resp.json()["expires_at"] is None


def test_reveal_share_link_returns_raw_token(client: Any) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]
    resp = client.post(f"/api/profile/share-links/{link_id}/reveal")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == data["token"]
    assert body["token"].startswith("lp_")


def test_reveal_share_link_404_for_other_user(
    client: Any, create_user_with_key: Any
) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]

    user_b, key_b = create_user_with_key(email="other@example.com")
    resp = client.post(
        f"/api/profile/share-links/{link_id}/reveal",
        headers={"X-API-Key": key_b},
    )
    assert resp.status_code == 404


def test_reveal_share_link_404_for_revoked(client: Any) -> None:
    data = _create_share_link(client)
    link_id = data["link"]["id"]

    # Revoke
    client.delete(f"/api/profile/share-links/{link_id}")

    resp = client.post(f"/api/profile/share-links/{link_id}/reveal")
    assert resp.status_code == 404


def test_reveal_share_link_404_for_legacy_without_token(client: Any, session: Session) -> None:
    """Legacy links with token=None cannot be revealed."""
    from app.auth import get_public_profile_token_prefix, hash_public_profile_token
    from app.models import PublicProfileLink

    token_hash = hash_public_profile_token("lp_fake_legacy_token")
    link = PublicProfileLink(
        user_id=1,
        name="Legacy",
        token_prefix=get_public_profile_token_prefix("lp_fake_legacy_token"),
        token_hash=token_hash,
    )
    session.add(link)
    session.commit()
    session.refresh(link)

    resp = client.post(f"/api/profile/share-links/{link.id}/reveal")
    assert resp.status_code == 404