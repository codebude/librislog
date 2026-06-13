"""Embed HTML widget endpoints for iframe dashboard integrations."""

import html
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session, select

from app.auth import EMBED_TOKEN_SCOPE_STATS_READ, hash_embed_token
from app.database import get_session
from app.models import Book, EmbedToken, ReadingStatus, User
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embed/v1", tags=["embed"])

VALID_STAT_KEYS = {"books", "reading", "read", "to_read", "pages", "avg_pages"}
LAYOUT_MODES = {"grid", "list"}


def _load_stat_labels() -> dict[str, dict[str, str]]:
    import json

    i18n_dir = Path(__file__).resolve().parent.parent / "i18n"
    required = {"books", "reading", "read", "to_read", "pages", "avg_pages"}
    loaded: dict[str, dict[str, str]] = {}

    for file_path in i18n_dir.glob("*.json"):
        locale = file_path.stem.lower()
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        stats_labels = data.get("embed", {}).get("stats", {})
        if not isinstance(stats_labels, dict):
            continue

        missing = required - set(stats_labels.keys())
        if missing:
            raise RuntimeError(
                f"Invalid i18n file {file_path.name}: missing embed.stats keys {', '.join(sorted(missing))}"
            )
        loaded[locale] = {k: str(v) for k, v in stats_labels.items() if k in required}

    if "en" not in loaded:
        raise RuntimeError("Invalid i18n files: expected at least en.json with embed.stats labels")

    return loaded


STAT_LABELS = _load_stat_labels()


def _normalize_lang(lang: str) -> str:
    base = (lang or "en").strip().lower().replace("_", "-").split("-", 1)[0]
    return base if base in STAT_LABELS else "en"


def _verify_embed_token(
    token: str,
    session: Session,
    request: Request,
) -> User:
    token_hash_val = hash_embed_token(token)
    db_token = session.exec(
        select(EmbedToken).where(
            EmbedToken.token_hash == token_hash_val,
            EmbedToken.revoked_at.is_(None),
        )
    ).first()

    if not db_token:
        logger.warning("Embed auth: invalid token prefix=%s", token[:12])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked token",
        )

    if db_token.expires_at and db_token.expires_at < utcnow():
        logger.warning(
            "Embed auth: expired token id=%s user=%s",
            db_token.id, db_token.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    scopes = [s.strip() for s in db_token.scopes.split(",")]
    if EMBED_TOKEN_SCOPE_STATS_READ not in scopes:
        logger.warning(
            "Embed auth: missing scope token id=%s scopes=%s",
            db_token.id, db_token.scopes,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token lacks required scope",
        )

    if db_token.allowed_origins:
        origin = request.headers.get("origin") or request.headers.get("referer") or ""
        if origin:
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            request_origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        else:
            request_origin = ""

        allowed = [
            o.strip().lower()
            for o in db_token.allowed_origins.split(",")
            if o.strip()
        ]
        if request_origin and request_origin not in allowed:
            logger.warning(
                "Embed auth: origin denied token id=%s user=%s origin=%s allowed=%s",
                db_token.id, db_token.user_id, request_origin, allowed,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin not allowed",
            )

    user = session.get(User, db_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token user not found",
        )

    db_token.last_used_at = utcnow()
    session.add(db_token)
    session.commit()

    return user


def _compute_stats(books: list[Book]) -> dict[str, int]:
    total = len(books)
    read = sum(1 for b in books if b.reading_status == ReadingStatus.read)
    reading = sum(1 for b in books if b.reading_status == ReadingStatus.currently_reading)
    want_to_read = sum(1 for b in books if b.reading_status == ReadingStatus.want_to_read)
    pages = sum(b.page_count or 0 for b in books if b.page_count)
    avg_pages = round(pages / total, 0) if total > 0 else 0
    return {
        "books": total,
        "reading": reading,
        "read": read,
        "to_read": want_to_read,
        "pages": pages,
        "avg_pages": int(avg_pages),
    }


def _render_stats_html(
    stats: dict[str, int],
    theme: str,
    accent: str,
    radius: str,
    density: str,
    hide_labels: bool,
    lang: str,
    font_scale: float,
    layout: str,
    show: Optional[set[str]] = None,
) -> str:
    density_gap = {"compact": "0.25rem", "normal": "0.5rem", "comfortable": "0.75rem"}.get(density, "0.5rem")
    radius_map = {"none": "0", "sm": "0.375rem", "md": "0.5rem", "lg": "0.75rem", "xl": "1rem"}.get(radius, "0.5rem")

    bg = "#ffffff" if theme == "light" else "#1d232a"
    fg = "#1f2937" if theme == "light" else "#e5e7eb"
    muted = "#6b7280" if theme == "light" else "#9ca3af"
    card_bg = "#f3f4f6" if theme == "light" else "#2a323d"
    card_border = "#e5e7eb" if theme == "light" else "#3d4452"

    base_font_size = f"{round(14 * font_scale, 1)}px"

    card_style = (
        f"background:{card_bg};border:1px solid {card_border};"
        f"border-radius:{radius_map};padding:{density_gap};"
        f"text-align:center;min-width:0"
    )

    parts: list[str] = []

    labels = STAT_LABELS[_normalize_lang(lang)]

    if show:
        keys = [k for k in VALID_STAT_KEYS if k in show]
    else:
        keys = ["books", "reading", "read", "to_read", "pages", "avg_pages"]

    items = [(labels[k], stats.get(k, 0)) for k in keys]

    if layout == "list":
        parts.append(f"<div style='display:flex;flex-direction:column;gap:{density_gap}'>")
        cols_per_row = 1
    else:
        cols_per_row = min(len(items), 3)
        if cols_per_row == 0:
            cols_per_row = 1
        parts.append(f"<div style='display:grid;grid-template-columns:repeat({cols_per_row},1fr);gap:{density_gap}'>")

    for label, value in items:
        parts.append(f"<div style='{card_style}'>")
        parts.append(
            f"<div style='font-size:1.3em;font-weight:700;color:{accent};'"
            f">{html.escape(str(value))}</div>"
        )
        if not hide_labels:
            parts.append(
                f"<div style='font-size:0.65em;color:{muted};"
                f"margin-top:0.125rem;white-space:nowrap'>"
                f"{html.escape(label)}</div>"
            )
        parts.append("</div>")
    parts.append("</div>")

    body = "".join(parts)

    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}">
<head>
<meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
font-size:{base_font_size};background:{bg};color:{fg};padding:{density_gap};line-height:1.4}}
a{{color:{accent}}}
</style>
</head>
<body>
{body}
</body>
</html>"""


@router.get("/stats", response_class=HTMLResponse)
def get_embed_stats(
    request: Request,
    token: str = Query(..., description="Embed token"),
    theme: str = Query("light", description="Theme: light|dark"),
    accent: str = Query("#3b82f6", description="Accent hex color"),
    radius: str = Query("md", description="Border radius: none|sm|md|lg|xl"),
    density: str = Query("normal", description="Density: compact|normal|comfortable"),
    hide_labels: bool = Query(False, description="Hide text labels"),
    show: Optional[str] = Query(None, description="Comma-separated stat keys to display"),
    lang: str = Query("en", description="HTML lang attribute"),
    font_scale: float = Query(1.0, ge=0.5, le=3.0, description="Font size multiplier"),
    layout: str = Query("grid", description="Layout: grid|list"),
    session: Session = Depends(get_session),
):
    user = _verify_embed_token(token, session, request)

    books = list(
        session.exec(
            select(Book).where(Book.user_id == user.id)
        ).all()
    )

    stats = _compute_stats(books)

    show_set: Optional[set[str]] = None
    if show:
        keys = {k.strip() for k in show.split(",") if k.strip()}
        invalid = keys - VALID_STAT_KEYS
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid stat keys: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(VALID_STAT_KEYS))}",
            )
        show_set = keys if keys else None

    if layout not in LAYOUT_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid layout '{layout}'. Valid: {', '.join(sorted(LAYOUT_MODES))}",
        )

    html_content = _render_stats_html(
        stats, theme, accent, radius, density, hide_labels, lang, font_scale, layout, show_set,
    )

    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors *",
        },
    )
