"""
Book import service.

Search priority:
  1. Open Library  (no API key required)
  2. Google Books  (optional API key, used as fallback)

Both return a list of BookImportCandidate objects normalised to the same schema.
"""

import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Literal, Optional

import httpx
import pycountry

from app.schemas import BookImportCandidate

logger = logging.getLogger(__name__)

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

GOOGLE_BOOKS_SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"

# 5xx codes that are worth retrying (transient backend / rate-limit errors)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3          # up to 3 extra attempts after the first try
_RETRY_BASE_DELAY = 1.0   # seconds — doubles each attempt (1 → 2 → 4)

# Google Books imageLinks size keys in preference order (largest first)
_COVER_SIZE_PREFERENCE = ["extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail"]
# Minimum acceptable file size — anything smaller is likely a placeholder/error page
_MIN_COVER_BYTES = 5_000


# ── Public API ────────────────────────────────────────────────────────────────

async def search_with_progress(
    query: str,
    search_type: str,
    *,
    api_key: str = "",
    mode: Literal["auto", "google_only"] = "auto",
    http_client: Optional[httpx.AsyncClient] = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that performs the same search as search() but yields
    progress events as dicts so the caller can stream them to the client.

    Event shapes (stage / extra fields):
      open_library  / status=searching
      open_library  / status=done, count=int
      google_books  / status=searching
      google_books  / status=done, count=int
      google_books  / status=skipped, reason=str
      complete      / results=list[dict]
      error         / message=str
    """
    logger.debug(
        "search_with_progress() called — query=%r search_type=%r has_api_key=%s",
        query, search_type, bool(api_key),
    )

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=10.0)

    try:
        ol_results: list[BookImportCandidate] = []
        gb_results: list[BookImportCandidate] = []

        if mode == "google_only":
            if not api_key:
                logger.warning("Google-only search requested for %r but API key is not set", query)
                yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
            else:
                yield {"stage": "google_books", "status": "searching"}
                gb_results = await _search_google_books(query, search_type, api_key, client)
                logger.info("Google Books returned %d result(s) for %r", len(gb_results), query)
                yield {"stage": "google_books", "status": "done", "count": len(gb_results)}
            results = gb_results
        else:
            yield {"stage": "open_library", "status": "searching"}
            ol_results = await _search_open_library(query, search_type, client)
            logger.info("Open Library returned %d result(s) for %r", len(ol_results), query)
            yield {"stage": "open_library", "status": "done", "count": len(ol_results)}

            if not ol_results:
                if not api_key:
                    logger.warning(
                        "No Open Library results for %r and GOOGLE_BOOKS_API_KEY is not set",
                        query,
                    )
                    yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
                else:
                    logger.info("No Open Library results — falling back to Google Books")
                    yield {"stage": "google_books", "status": "searching"}
                    gb_results = await _search_google_books(query, search_type, api_key, client)
                    logger.info("Google Books returned %d result(s) for %r", len(gb_results), query)
                    yield {"stage": "google_books", "status": "done", "count": len(gb_results)}

            results = ol_results or gb_results

        yield {"stage": "complete", "results": [r.model_dump() for r in results]}
    except Exception as exc:
        logger.exception("search_with_progress error: %s", exc)
        yield {"stage": "error", "message": str(exc)}
    finally:
        if own_client:
            await client.aclose()


async def search(
    query: str,
    search_type: str,
    *,
    api_key: str = "",
    http_client: Optional[httpx.AsyncClient] = None,
) -> list[BookImportCandidate]:
    """Search Open Library first; fall back to Google Books if no results."""
    logger.debug("search() called — query=%r search_type=%r has_api_key=%s",
                 query, search_type, bool(api_key))

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=10.0)

    try:
        results = await _search_open_library(query, search_type, client)
        logger.info("Open Library returned %d result(s) for %r", len(results), query)

        if not results:
            if not api_key:
                logger.warning(
                    "No Open Library results for %r and GOOGLE_BOOKS_API_KEY is not set — "
                    "Google Books requires an API key for all requests. "
                    "Set GOOGLE_BOOKS_API_KEY in .env to enable the fallback.",
                    query,
                )
            else:
                logger.info("No Open Library results — falling back to Google Books")
                results = await _search_google_books(query, search_type, api_key, client)
                logger.info("Google Books returned %d result(s) for %r", len(results), query)

        return results
    finally:
        if own_client:
            await client.aclose()


# ── Open Library ──────────────────────────────────────────────────────────────

async def _search_open_library(
    query: str,
    search_type: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    if search_type == "isbn":
        params = {
            "q": f"isbn:{query}",
            "fields": "title,author_name,isbn,publisher,first_publish_year,number_of_pages_median,subject,cover_i,language",
            "limit": 5,
        }
    else:
        params = {
            "q": query,
            "fields": "title,author_name,isbn,publisher,first_publish_year,number_of_pages_median,subject,cover_i,language",
            "limit": 10,
        }

    logger.debug("Open Library request — url=%s params=%s", OPEN_LIBRARY_SEARCH_URL, params)

    try:
        resp = await client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
        logger.debug("Open Library response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Open Library HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        return []
    except httpx.HTTPError as exc:
        logger.warning("Open Library request failed: %s", exc)
        return []

    docs = resp.json().get("docs", [])
    logger.debug("Open Library docs in response: %d", len(docs))
    candidates = [map_open_library(doc) for doc in docs if doc.get("title")]
    for c in candidates:
        logger.debug("  OL candidate: title=%r isbn=%r", c.title, c.isbn)
    return candidates


def map_open_library(doc: dict) -> BookImportCandidate:
    """Map a single Open Library search doc to BookImportCandidate."""
    # Authors: list of strings
    authors = doc.get("author_name") or []
    author = ", ".join(authors) if authors else None

    # ISBN: first entry of the list, prefer ISBN-13 (length 13)
    isbns: list[str] = doc.get("isbn") or []
    isbn = _pick_isbn(isbns)

    # Cover image
    cover_id = doc.get("cover_i")
    cover_url = OPEN_LIBRARY_COVER_URL.format(cover_id=cover_id) if cover_id else None

    # Publisher: first entry
    publishers: list[str] = doc.get("publisher") or []
    publisher = publishers[0] if publishers else None

    # Genres: first 3 subjects joined
    subjects: list[str] = doc.get("subject") or []
    genre = ", ".join(subjects[:3]) if subjects else None

    # Language: Open Library returns list[str] of ISO 639-2 codes (e.g. ["eng"])
    languages: list[str] = doc.get("language") or []
    language = _normalize_language_code(languages[0] if languages else None)

    return BookImportCandidate(
        title=doc["title"],
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=doc.get("first_publish_year"),
        page_count=doc.get("number_of_pages_median"),
        language=language,
        genre=genre,
        source="open_library",
    )


# ── Google Books ──────────────────────────────────────────────────────────────

async def _search_google_books(
    query: str,
    search_type: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    if search_type == "isbn":
        q = f"isbn:{query}"
    else:
        q = query

    params: dict = {"q": q, "maxResults": 10}
    if api_key:
        params["key"] = api_key

    logger.debug("Google Books request — url=%s params=%s",
                 GOOGLE_BOOKS_SEARCH_URL,
                 {k: v for k, v in params.items() if k != "key"})

    resp = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await client.get(GOOGLE_BOOKS_SEARCH_URL, params=params)
            logger.debug("Google Books response — status=%d body_size=%d bytes (attempt %d)",
                         resp.status_code, len(resp.content), attempt + 1)
        except httpx.HTTPError as exc:
            logger.warning("Google Books request failed (attempt %d): %s", attempt + 1, exc)
            return []

        if resp.status_code in _RETRYABLE_STATUSES and attempt < _MAX_RETRIES:
            delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.25)
            logger.warning(
                "Google Books returned %d on attempt %d/%d — retrying in %.2fs",
                resp.status_code, attempt + 1, _MAX_RETRIES + 1, delay,
            )
            await asyncio.sleep(delay)
            continue

        break  # success or non-retryable error — exit loop

    if resp is None:
        return []

    if not resp.is_success:
        logger.warning("Google Books HTTP error: %s — body: %s",
                       resp.status_code, resp.text[:500])
        return []

    body = resp.json()
    items = body.get("items") or []
    logger.debug("Google Books items in response: %d (totalItems=%s)",
                 len(items), body.get("totalItems", "n/a"))

    if not items and "error" in body:
        logger.warning("Google Books API error payload: %s", body["error"])

    items = [item for item in items if item.get("volumeInfo", {}).get("title")]

    # Resolve the best available cover for each item in parallel
    cover_urls: list[str | None] = list(await asyncio.gather(*[
        _best_google_books_cover(
            item.get("id"),
            item.get("volumeInfo", {}).get("imageLinks", {}).get("thumbnail"),
            client,
        )
        for item in items
    ]))

    candidates = []
    for item, cover_url in zip(items, cover_urls):
        candidate = map_google_books(item)
        # Override whatever map_google_books picked with the resolved best cover
        candidate = candidate.model_copy(update={"cover_url": cover_url})
        candidates.append(candidate)
        logger.debug("  GB candidate: title=%r isbn=%r cover=%r",
                     candidate.title, candidate.isbn, candidate.cover_url)
    return candidates


async def _best_google_books_cover(
    item_id: str | None,
    fallback_url: str | None,
    client: httpx.AsyncClient,
) -> str | None:
    """
    Fetch the full volume record to get high-res imageLinks, then probe each
    size URL (extraLarge → large → medium → small → thumbnail → smallThumbnail)
    via a HEAD request.  A URL is accepted when it returns HTTP 200 with either:
      - a content-type of image/* and no content-length (CDN omits it), or
      - a content-length exceeding _MIN_COVER_BYTES (filters placeholder pages).
    Falls back to the search-result thumbnail when nothing better is available.
    """
    # ── 1. Fetch full volume to get all imageLink sizes ────────────────────────
    image_links: dict = {}
    if item_id:
        try:
            resp = await client.get(f"{GOOGLE_BOOKS_SEARCH_URL}/{item_id}")
            resp.raise_for_status()
            image_links = resp.json().get("volumeInfo", {}).get("imageLinks", {})
            logger.debug("Volume %s imageLinks keys: %s", item_id, list(image_links))
        except httpx.HTTPError as exc:
            logger.debug("Could not fetch volume %s for cover resolution: %s", item_id, exc)

    # ── 2. Build candidate list in preference order ───────────────────────────
    candidates: list[str] = []
    for size in _COVER_SIZE_PREFERENCE:
        url = image_links.get(size)
        if url:
            candidates.append(url.replace("http://", "https://"))

    # Ensure the search-result thumbnail is always available as last resort
    if fallback_url:
        clean_fallback = fallback_url.replace("http://", "https://")
        if clean_fallback not in candidates:
            candidates.append(clean_fallback)

    # ── 3. Probe each candidate with a HEAD request ───────────────────────────
    for url in candidates:
        try:
            head = await client.head(url, follow_redirects=True)
            if head.status_code != 200:
                logger.debug("Cover %s → HTTP %d, skipping", url, head.status_code)
                continue
            content_type = head.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.debug("Cover %s → non-image content-type %r, skipping", url, content_type)
                continue
            content_length = int(head.headers.get("content-length", 0))
            if 0 < content_length < _MIN_COVER_BYTES:
                logger.debug("Cover %s → too small (%d bytes), skipping", url, content_length)
                continue
            logger.debug("Best cover for volume %s: %s (%d bytes)", item_id, url, content_length)
            return url
        except httpx.HTTPError as exc:
            logger.debug("HEAD %s failed: %s", url, exc)
            continue

    # Nothing validated — return raw fallback (may be None)
    return fallback_url.replace("http://", "https://") if fallback_url else None


def map_google_books(item: dict) -> BookImportCandidate:
    """Map a single Google Books volume item to BookImportCandidate."""
    vi = item.get("volumeInfo", {})

    # Authors
    authors: list[str] = vi.get("authors") or []
    author = ", ".join(authors) if authors else None

    # ISBN: prefer ISBN_13
    identifiers: list[dict] = vi.get("industryIdentifiers") or []
    isbns_13 = [i["identifier"] for i in identifiers if i.get("type") == "ISBN_13"]
    isbns_10 = [i["identifier"] for i in identifiers if i.get("type") == "ISBN_10"]
    isbn = (isbns_13 or isbns_10 or [None])[0]

    # Cover image: use thumbnail, upgrade to https
    image_links: dict = vi.get("imageLinks") or {}
    cover_url = image_links.get("thumbnail")
    if cover_url:
        cover_url = cover_url.replace("http://", "https://")

    # Published year: publishedDate can be "YYYY", "YYYY-MM", or "YYYY-MM-DD"
    published_date: Optional[str] = vi.get("publishedDate")
    published_year: Optional[int] = None
    if published_date:
        try:
            published_year = int(published_date[:4])
        except (ValueError, IndexError):
            pass

    # Genres
    categories: list[str] = vi.get("categories") or []
    genre = ", ".join(categories[:3]) if categories else None

    # Language: Google Books uses ISO 639-1 (e.g. "en")
    language = _normalize_language_code(vi.get("language"))

    return BookImportCandidate(
        title=vi["title"],
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        publisher=vi.get("publisher"),
        published_year=published_year,
        page_count=vi.get("pageCount"),
        language=language,
        genre=genre,
        source="google_books",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_isbn(isbns: list[str]) -> Optional[str]:
    """Return the first ISBN-13 found, or the first ISBN-10, or None."""
    for isbn in isbns:
        clean = isbn.replace("-", "").replace(" ", "")
        if len(clean) == 13 and clean.isdigit():
            return clean
    for isbn in isbns:
        clean = isbn.replace("-", "").replace(" ", "")
        if len(clean) == 10 and clean[:9].isdigit():
            return clean
    return isbns[0] if isbns else None


def _normalize_language_code(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip().lower()
    if not normalized.isalpha():
        return None

    lang = None
    if len(normalized) == 2:
        lang = pycountry.languages.get(alpha_2=normalized)
    elif len(normalized) == 3:
        # Open Library may return either terminology (fra) or bibliographic (fre) ISO 639-2 codes.
        lang = pycountry.languages.get(alpha_3=normalized)
        if lang is None:
            lang = pycountry.languages.get(bibliographic=normalized)
    else:
        return None

    alpha_2 = getattr(lang, "alpha_2", None)
    return alpha_2.upper() if alpha_2 else None
