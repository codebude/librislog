"""Tests for dashboard gamification — reading streaks and reading goals."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import Book, ReadingProgress, UserSettings
from app.routers.statistics import current_streak, longest_streak


def _create_book(client: Any, **overrides: Any) -> dict[str, Any]:
    """Helper to create a book via the API and return the JSON response."""
    payload = {"title": "Book", "author": "Test Author", "page_count": 100, **overrides}
    resp = client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _add_progress(session: Session, book: dict[str, Any], page: int, when: datetime) -> None:
    db_book = session.get(Book, book["id"])
    assert db_book is not None
    assert db_book.id is not None
    assert db_book.user_id is not None
    session.add(
        ReadingProgress(
            book_id=db_book.id, user_id=db_book.user_id, page=page, created_at=when
        )
    )
    session.commit()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(days: int) -> datetime:
    return _utc_now() - timedelta(days=days)


def test_current_streak_today_active() -> None:
    today = date(2026, 8, 26)
    assert current_streak({"2026-08-26"}, today) == 1
    assert current_streak({"2026-08-26", "2026-08-25", "2026-08-24"}, today) == 3
    assert current_streak({"2026-08-26", "2026-08-24"}, today) == 1


def test_current_streak_does_not_break_when_today_not_logged() -> None:
    today = date(2026, 8, 26)
    assert current_streak({"2026-08-25"}, today) == 1
    assert current_streak({"2026-08-25", "2026-08-24", "2026-08-23"}, today) == 3


def test_current_streak_breaks_when_yesterday_not_logged() -> None:
    today = date(2026, 8, 26)
    assert current_streak({"2026-08-24"}, today) == 0
    assert current_streak({"2026-08-26", "2026-08-24"}, today) == 1
    assert current_streak(set(), today) == 0


def test_longest_streak_finds_longest_run_and_most_recent_tie() -> None:
    active = {
        "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
        "2026-01-10", "2026-01-11", "2026-01-12",
    }
    assert longest_streak(active) == (5, "2026-01-01", "2026-01-05")

    tie = {"2026-01-01", "2026-01-02", "2026-03-01", "2026-03-02"}
    assert longest_streak(tie) == (2, "2026-03-01", "2026-03-02")


def test_longest_streak_single_day_and_empty() -> None:
    assert longest_streak({"2026-06-01"}) == (1, "2026-06-01", "2026-06-01")
    assert longest_streak(set()) == (0, None, None)


# ── API: streaks ───────────────────────────────────────────────────────────────


def test_gamification_empty_library(client: Any) -> None:
    resp = client.get("/api/statistics/gamification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_streak"] == 0
    assert data["longest_streak"] == 0
    assert data["longest_streak_start"] is None
    assert data["longest_streak_end"] is None
    assert data["goals"] == []


def test_gamification_current_streak_today_logged(client: Any, session: Session) -> None:
    book = _create_book(client)
    _add_progress(session, book, 10, _utc_now())

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] >= 1
    assert data["longest_streak"] >= 1


def test_gamification_current_streak_multiple_consecutive_days(client: Any, session: Session) -> None:
    book = _create_book(client)
    for day in range(3):
        _add_progress(session, book, 10 + day, _days_ago(day))

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] == 3


def test_gamification_streak_does_not_break_without_today(client: Any, session: Session) -> None:
    book = _create_book(client)
    for day in (1, 2):
        _add_progress(session, book, 10 + day, _days_ago(day))

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] == 2


def test_gamification_streak_breaks_after_gap(client: Any, session: Session) -> None:
    book = _create_book(client)
    _add_progress(session, book, 5, _days_ago(3))

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] == 0


def test_gamification_longest_streak_returns_window(client: Any, session: Session) -> None:
    book = _create_book(client)
    # two runs: 3 consecutive days ending today, and a longer 4-day run 10+ days ago
    for day in range(3):
        _add_progress(session, book, 20 + day, _days_ago(day))
    for day in range(10, 14):
        _add_progress(session, book, 30 + day, _days_ago(day))

    data = client.get("/api/statistics/gamification").json()
    assert data["longest_streak"] == 4
    assert data["longest_streak_start"] is not None
    assert data["longest_streak_end"] is not None


def test_gamification_timezone_aware_streak(client: Any, session: Session) -> None:
    settings = session.exec(select(UserSettings)).first()
    assert settings is not None
    settings.timezone = "America/New_York"
    session.add(settings)
    session.commit()

    book = _create_book(client)
    _add_progress(session, book, 10, _utc_now())

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] == 1


# ── API: goals ─────────────────────────────────────────────────────────────────


def _set_goal(session: Session, enabled_col: str, target_col: str, enabled: bool, target: int) -> None:
    settings = session.exec(select(UserSettings)).first()
    assert settings is not None
    setattr(settings, enabled_col, enabled)
    setattr(settings, target_col, target)
    session.add(settings)
    session.commit()


def test_gamification_goals_disabled_by_default(client: Any, session: Session) -> None:
    book = _create_book(client)
    _add_progress(session, book, 10, _utc_now())

    data = client.get("/api/statistics/gamification").json()
    assert data["goals"] == []


def test_gamification_goal_pages_per_day(client: Any, session: Session) -> None:
    _set_goal(session, "goal_pages_per_day_enabled", "goal_pages_per_day", True, 20)
    book = _create_book(client)
    _add_progress(session, book, 5, _days_ago(1))
    _add_progress(session, book, 15, _utc_now())

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert len(goals) == 1
    assert goals[0]["type"] == "pages_per_day"
    assert goals[0]["target"] == 20
    assert goals[0]["current"] == 10
    assert goals[0]["reached"] is False


def test_gamification_goal_pages_per_day_reached(client: Any, session: Session) -> None:
    _set_goal(session, "goal_pages_per_day_enabled", "goal_pages_per_day", True, 20)
    book = _create_book(client)
    _add_progress(session, book, 5, _days_ago(1))
    _add_progress(session, book, 30, _utc_now())

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert goals[0]["current"] == 25
    assert goals[0]["reached"] is True


def test_gamification_goal_pages_per_month(client: Any, session: Session) -> None:
    _set_goal(session, "goal_pages_per_month_enabled", "goal_pages_per_month", True, 300)
    book = _create_book(client)
    # Two entries on the same day keep the delta fully inside the current month.
    now = _utc_now()
    _add_progress(session, book, 50, now)
    _add_progress(session, book, 200, now)

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert len(goals) == 1
    assert goals[0]["type"] == "pages_per_month"
    assert goals[0]["current"] == 150
    assert goals[0]["reached"] is False


def test_gamification_goal_pages_per_month_fallback_book(client: Any, session: Session) -> None:
    _set_goal(session, "goal_pages_per_month_enabled", "goal_pages_per_month", True, 300)
    now = _utc_now()
    _create_book(
        client,
        title="Fallback month pages",
        reading_status="read",
        page_count=100,
        date_started=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_finished=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert goals[0]["current"] == 100


def test_gamification_goal_books_per_month(client: Any, session: Session) -> None:
    _set_goal(session, "goal_books_per_month_enabled", "goal_books_per_month", True, 2)
    now = _utc_now()
    for i in range(2):
        _create_book(
            client,
            title=f"Finished {i}",
            reading_status="read",
            date_started=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            date_finished=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert len(goals) == 1
    assert goals[0]["type"] == "books_per_month"
    assert goals[0]["current"] == 2
    assert goals[0]["reached"] is True


def test_gamification_goal_books_per_year(client: Any, session: Session) -> None:
    _set_goal(session, "goal_books_per_year_enabled", "goal_books_per_year", True, 2)
    now = _utc_now()
    _create_book(
        client,
        title="Finished this year",
        reading_status="read",
        date_started=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_finished=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert len(goals) == 1
    assert goals[0]["type"] == "books_per_year"
    assert goals[0]["current"] == 1
    assert goals[0]["reached"] is False


def test_gamification_fallback_finished_book_counts_as_active_day(client: Any, session: Session) -> None:
    now = _utc_now()
    _create_book(
        client,
        title="No progress, finished today",
        reading_status="read",
        page_count=150,
        date_started=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_finished=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    # fallback books must have NO progress entries at all
    assert session.exec(select(ReadingProgress)).first() is None

    data = client.get("/api/statistics/gamification").json()
    assert data["current_streak"] == 1
    assert data["longest_streak"] == 1
    assert data["longest_streak_end"] is not None


def test_gamification_fallback_book_page_count_counts_toward_daily_goal(
    client: Any, session: Session,
) -> None:
    _set_goal(session, "goal_pages_per_day_enabled", "goal_pages_per_day", True, 200)
    now = _utc_now()
    _create_book(
        client,
        title="Fallback pages",
        reading_status="read",
        page_count=150,
        date_started=(now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        date_finished=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    goals = client.get("/api/statistics/gamification").json()["goals"]
    assert goals[0]["current"] == 150


# ── API: goal settings validation ─────────────────────────────────────────────


def test_settings_goal_target_below_minimum_rejected(client: Any) -> None:
    resp = client.patch("/api/profile/settings", json={"goal_pages_per_day": 0})
    assert resp.status_code == 422


def test_settings_goal_target_negative_rejected(client: Any) -> None:
    resp = client.patch("/api/profile/settings", json={"goal_books_per_year": -3})
    assert resp.status_code == 422


def test_settings_goal_target_valid_saved(client: Any) -> None:
    resp = client.patch(
        "/api/profile/settings",
        json={"goal_pages_per_day": 25, "goal_pages_per_day_enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_pages_per_day"] == 25
    assert data["goal_pages_per_day_enabled"] is True
    assert data["goal_books_per_month"] == 2
    assert data["goal_books_per_year"] == 25


def test_gamification_without_settings_row_uses_defaults(client: Any, session: Session) -> None:
    for settings in session.exec(select(UserSettings)).all():
        session.delete(settings)
    session.commit()

    resp = client.get("/api/statistics/gamification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_streak"] == 0
    assert data["goals"] == []


def test_gamification_enabled_by_default(client: Any, session: Session) -> None:
    book = _create_book(client)
    _add_progress(session, book, 10, _utc_now())

    data = client.get("/api/statistics/gamification").json()
    assert data["enabled"] is True


def test_gamification_disabled_returns_empty(client: Any, session: Session) -> None:
    _set_goal(session, "goal_pages_per_day_enabled", "goal_pages_per_day", True, 20)
    settings = session.exec(select(UserSettings)).first()
    assert settings is not None
    settings.gamification_enabled = False
    session.add(settings)
    session.commit()

    book = _create_book(client)
    _add_progress(session, book, 10, _utc_now())

    data = client.get("/api/statistics/gamification").json()
    assert data["enabled"] is False
    assert data["current_streak"] == 0
    assert data["longest_streak"] == 0
    assert data["goals"] == []


def test_settings_gamification_enabled_saved(client: Any) -> None:
    resp = client.patch("/api/profile/settings", json={"gamification_enabled": False})
    assert resp.status_code == 200
    assert resp.json()["gamification_enabled"] is False