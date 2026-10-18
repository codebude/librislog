"""
Book import service.

Search priority:
  1. Open Library  (no API key required)
  2. BnF            (no API key required)
  3. Inventaire     (no API key required, ISBN-only)
  4. Library of Congress (no API key required)
  5. Hardcover      (API token required, skipped if not configured)
  6. Google Books   (optional API key, used as fallback when all above return empty)

All return a list of BookImportCandidate objects normalised to the same schema.
"""

import asyncio
import logging
import random
import re
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, Optional

import httpx
import pycountry
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from app.config import settings
from app.schemas import BookImportCandidate
from app.services.cover_import import is_safe_cover_import_url
from app.services.isbn_utils import normalize_isbn

logger = logging.getLogger(__name__)

OPEN_LIBRARY_SEARCH_URL: str = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL: str = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

BNF_SRU_URL: str = "https://catalogue.bnf.fr/api/SRU"
INVENTAIRE_ENTITIES_URL: str = "https://inventaire.io/api/entities/by-uris"
LOC_SRU_URL: str = "http://lx2.loc.gov:210/LCDB"
DNB_SRU_URL: str = "https://services.dnb.de/sru/dnb"

INVENTAIRE_COVER_BASE_URL: str = "https://inventaire.io/img/entities"

# The LoC SRU server listens on plain HTTP port 210, which is frequently blocked or
# silently dropped by egress firewalls. Give it a shorter budget than the shared
# client so a blocked LoC cannot hold up the whole search.
_LOC_TIMEOUT_SECONDS: float = 5.0

_USER_AGENT: str = "LibrisLog/1.0 (book import; +https://github.com/codebude/librislog)"

GOOGLE_BOOKS_SEARCH_URL: str = "https://www.googleapis.com/books/v1/volumes"

HARDCOVER_GRAPHQL_URL: str = "https://api.hardcover.app/v1/graphql"

HARDCOVER_SEARCH_QUERY: str = """
query SearchQuery($q: String!) {
  search(query: $q, query_type: "book", per_page: 1, page: 1) {
    results
  }
}
"""

HARDCOVER_BOOK_MAPPINGS_QUERY: str = """
query BookMappingsQuery($where: book_mappings_bool_exp!) {
  book_mappings(limit: 10, where: $where) {
    edition {
      title
      subtitle
      isbn_13
      pages
      release_date
      image { url }
      publisher { name }
      language { code2 }
      book {
        description
        taggings {
          tag { tag }
        }
      }
      contributions {
        author { name }
      }
    }
  }
}
"""

# 5xx codes that are worth retrying (transient backend / rate-limit errors)
_RETRYABLE_STATUSES: set[int] = {429, 500, 502, 503, 504}
_MAX_RETRIES: int = 3
_RETRY_BASE_DELAY: float = 1.0

# Google Books imageLinks size keys in preference order (largest first)
_COVER_SIZE_PREFERENCE: list[str] = ["extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail"]
_MIN_COVER_BYTES: int = 1_000


class SourceBackendError(Exception):
    """Raised when an external book source returns an error response."""

    def __init__(
        self,
        source: Literal[
            "open_library", "google_books", "hardcover", "bnf", "inventaire",
            "library_of_congress", "dnb"
        ],
        status_code: int | None = None,
    ) -> None:
        self.source = source
        self.status_code = status_code
        super().__init__(f"{source} backend error")


def _truncate_api_key(api_key: str) -> str:
    """Return a truncated version of an API key suitable for logging."""
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return f"{api_key[:2]}...{api_key[-2:]}"
    return f"{api_key[:4]}...{api_key[-4:]}"


# ── Source registry ───────────────────────────────────────────────────────────


def _ol_enabled() -> bool:
    return settings.open_library_import_search_enabled


def _bnf_enabled() -> bool:
    return settings.bnf_import_search_enabled


def _inventaire_enabled() -> bool:
    return settings.inventaire_import_search_enabled


def _loc_enabled() -> bool:
    return settings.library_of_congress_import_search_enabled


def _dnb_enabled() -> bool:
    return settings.dnb_import_search_enabled


def _hc_enabled() -> bool:
    return settings.hardcover_import_search_enabled


def _google_fallback_enabled() -> bool:
    """Return True when the Google Books fallback may run."""
    return settings.google_books_import_search_enabled


def _skip_reason(stage: str, search_type: str, hardcover_api_token: str) -> str | None:
    """Return why a source cannot run for this query, or None when it can.

    A skipped source is reported once and never queried, so the UI does not claim a
    search ran when nothing was sent.
    """
    if stage == "hardcover" and not hardcover_api_token.strip():
        return "no_api_token"
    if stage == "inventaire" and search_type != "isbn":
        # Inventaire exposes no usable title-search route.
        return "title_search_unsupported"
    return None


@dataclass(frozen=True)
class SourceSpec:
    """Configuration for a single book import search provider."""

    stage: str
    display_name: str
    enabled: Callable[[], bool]
    search: Callable[[str, str, httpx.AsyncClient], Awaitable[list[BookImportCandidate]]]


def _build_sources(hardcover_api_token: str) -> tuple[SourceSpec, ...]:
    """Return the parallel search sources in result-order.

    Hardcover is always listed so the UI can report it as skipped when no token is
    configured; its dispatcher is bound to the token passed by the caller rather than
    to settings, so an explicit token argument keeps working exactly as before.
    """
    return (
        SourceSpec(
            stage="open_library",
            display_name="Open Library",
            enabled=_ol_enabled,
            search=_dispatch_open_library,
        ),
        SourceSpec(
            stage="bnf",
            display_name="BnF",
            enabled=_bnf_enabled,
            search=_dispatch_bnf,
        ),
        SourceSpec(
            stage="inventaire",
            display_name="Inventaire",
            enabled=_inventaire_enabled,
            search=_dispatch_inventaire,
        ),
        SourceSpec(
            stage="library_of_congress",
            display_name="Library of Congress",
            enabled=_loc_enabled,
            search=_dispatch_loc,
        ),
        SourceSpec(
            stage="dnb",
            display_name="Deutsche Nationalbibliothek",
            enabled=_dnb_enabled,
            search=_dispatch_dnb,
        ),
        SourceSpec(
            stage="hardcover",
            display_name="Hardcover",
            enabled=_hc_enabled,
            search=_make_hardcover_dispatcher(hardcover_api_token),
        ),
    )


def _make_hardcover_dispatcher(
    api_token: str,
) -> Callable[[str, str, httpx.AsyncClient], Awaitable[list[BookImportCandidate]]]:
    """Build a Hardcover search callable bound to ``api_token``."""

    async def _dispatch(query: str, search_type: str, client: httpx.AsyncClient) -> list[BookImportCandidate]:
        if not api_token.strip():
            return []
        return await _search_hardcover(query, search_type, api_token, client)

    return _dispatch


# Indirection through module-level wrappers so tests can monkeypatch the
# underlying search functions (see tests/test_book_import.py).
async def _dispatch_open_library(
    query: str, search_type: str, client: httpx.AsyncClient
) -> list[BookImportCandidate]:
    return await _search_open_library(query, search_type, client)


async def _dispatch_bnf(
    query: str, search_type: str, client: httpx.AsyncClient
) -> list[BookImportCandidate]:
    return await _search_bnf(query, search_type, client)


async def _dispatch_inventaire(
    query: str, search_type: str, client: httpx.AsyncClient
) -> list[BookImportCandidate]:
    return await _search_inventaire(query, search_type, client)


async def _dispatch_loc(
    query: str, search_type: str, client: httpx.AsyncClient
) -> list[BookImportCandidate]:
    return await _search_loc(query, search_type, client)


async def _dispatch_dnb(
    query: str, search_type: str, client: httpx.AsyncClient
) -> list[BookImportCandidate]:
    return await _search_dnb(query, search_type, client)


# ── Public API ────────────────────────────────────────────────────────────────


async def search_with_progress(
    query: str,
    search_type: str,
    *,
    api_key: str = "",
    hardcover_api_token: str = "",
    mode: Literal["auto", "google_only"] = "auto",
    http_client: Optional[httpx.AsyncClient] = None,
) -> AsyncGenerator[dict, None]:
    """Search external book sources and yield progress events as dicts.

    Event shapes (stage / extra fields):
      All sources  / status=searching, done (count), error (reason), skipped (reason)
      complete     / results=list[dict]
      error        / message=str

    Args:
        query: Search query string.
        search_type: ``"title"`` or ``"isbn"``.
        api_key: Google Books API key (optional).
        hardcover_api_token: Hardcover.app API token (optional, legacy).
        mode: ``"auto"`` (all enabled sources, fallback to GB) or ``"google_only"``.
        http_client: Reusable httpx client (created internally if omitted).

    Yields:
        Progress event dicts, and finally a ``complete`` event with results.
    """
    logger.debug(
        "search_with_progress() called — query=%r search_type=%r has_api_key=%s has_hc_token=%s",
        query, search_type, bool(api_key), bool(hardcover_api_token),
    )

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": _USER_AGENT},
    )

    try:
        results: list[BookImportCandidate] = []

        if mode == "google_only":
            if not _google_fallback_enabled():
                logger.warning(
                    "Google-only search requested for %r but the Google Books source "
                    "is disabled (GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=false)",
                    query,
                )
                yield {"stage": "google_books", "status": "skipped", "reason": "disabled"}
            elif not api_key:
                logger.warning("Google-only search requested for %r but API key is not set", query)
                yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
            else:
                logger.debug(
                    "Google Books invocation — mode=%s query=%r search_type=%r api_key=%s",
                    mode, query, search_type, _truncate_api_key(api_key),
                )
                yield {"stage": "google_books", "status": "searching"}
                try:
                    gb_results = await _search_google_books(query, search_type, api_key, client)
                    logger.info("Google Books returned %d result(s) for %r", len(gb_results), query)
                    yield {"stage": "google_books", "status": "done", "count": len(gb_results)}
                    results = gb_results
                except SourceBackendError as exc:
                    logger.warning("Google Books backend error for %r: status=%s", query, exc.status_code)
                    yield {"stage": "google_books", "status": "error", "reason": "backend_error"}
        else:
            enabled_sources = [s for s in _build_sources(hardcover_api_token) if s.enabled()]

            if enabled_sources:
                all_events: dict[str, list[dict]] = {s.stage: [] for s in enabled_sources}
                all_results: dict[str, list[BookImportCandidate]] = {s.stage: [] for s in enabled_sources}

                # A source that cannot run for this query gets exactly one terminal
                # `skipped` event and is excluded from the gather, so it never also
                # reports a result count.
                runnable: list[SourceSpec] = []
                for s in enabled_sources:
                    reason = _skip_reason(s.stage, search_type, hardcover_api_token)
                    if reason is not None:
                        all_events[s.stage].append(
                            {"stage": s.stage, "status": "skipped", "reason": reason}
                        )
                    else:
                        all_events[s.stage].append({"stage": s.stage, "status": "searching"})
                        runnable.append(s)

                async def _run_source(spec: SourceSpec) -> None:
                    try:
                        r = await spec.search(query, search_type, client)
                        all_results[spec.stage] = r
                        all_events[spec.stage].append(
                            {"stage": spec.stage, "status": "done", "count": len(r)}
                        )
                    except SourceBackendError as exc:
                        logger.warning(
                            "%s backend error for %r: status=%s", spec.stage, query, exc.status_code
                        )
                        all_events[spec.stage].append(
                            {"stage": spec.stage, "status": "error", "reason": "backend_error"}
                        )
                    except Exception:
                        logger.exception("%s search error", spec.stage)
                        all_events[spec.stage].append(
                            {"stage": spec.stage, "status": "error", "reason": "backend_error"}
                        )

                await asyncio.gather(*[_run_source(s) for s in runnable])

                for s in enabled_sources:
                    for e in all_events[s.stage]:
                        yield e

                merged: list[BookImportCandidate] = []
                for s in runnable:
                    merged = _merge_results(merged, all_results[s.stage])
                results = merged
            else:
                # Every parallel source is switched off. Google Books can still answer
                # as the fallback, which is the only remaining provider.
                logger.warning(
                    "No parallel import search provider is enabled for %r — "
                    "only the Google Books fallback is available",
                    query,
                )

            if not results:
                if not _google_fallback_enabled():
                    logger.warning(
                        "No results for %r and the Google Books fallback is disabled "
                        "(GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=false)",
                        query,
                    )
                    yield {"stage": "google_books", "status": "skipped", "reason": "disabled"}
                elif not api_key:
                    logger.warning("No results for %r and GOOGLE_BOOKS_API_KEY is not set", query)
                    yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
                else:
                    logger.info("No results from any source — falling back to Google Books")
                    logger.debug(
                        "Google Books invocation — mode=%s query=%r search_type=%r api_key=%s",
                        mode, query, search_type, _truncate_api_key(api_key),
                    )
                    yield {"stage": "google_books", "status": "searching"}
                    try:
                        gb_results = await _search_google_books(query, search_type, api_key, client)
                        logger.info("Google Books returned %d result(s) for %r", len(gb_results), query)
                        yield {"stage": "google_books", "status": "done", "count": len(gb_results)}
                        results = gb_results
                    except SourceBackendError as exc:
                        logger.warning("Google Books backend error for %r: status=%s", query, exc.status_code)
                        yield {"stage": "google_books", "status": "error", "reason": "backend_error"}

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
    hardcover_api_token: str = "",
    http_client: Optional[httpx.AsyncClient] = None,
) -> list[BookImportCandidate]:
    """Search all enabled external book sources; fall back to Google Books if all return empty.

    Args:
        query: Search query string.
        search_type: ``"title"`` or ``"isbn"``.
        api_key: Google Books API key (optional).
        hardcover_api_token: Hardcover.app API token (optional, legacy).
        http_client: Reusable httpx client (created internally if omitted).

    Returns:
        A list of BookImportCandidate objects.
    """
    logger.debug("search() called — query=%r search_type=%r has_api_key=%s has_hc_token=%s",
                 query, search_type, bool(api_key), bool(hardcover_api_token))

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": _USER_AGENT},
    )

    try:
        enabled_sources = [s for s in _build_sources(hardcover_api_token) if s.enabled()]
        results: list[BookImportCandidate] = []

        if enabled_sources:
            all_results: list[list[BookImportCandidate]] = []

            async def _run_source(spec: SourceSpec) -> list[BookImportCandidate]:
                try:
                    r = await spec.search(query, search_type, client)
                    logger.info("%s returned %d result(s) for %r", spec.stage, len(r), query)
                    return r
                except SourceBackendError as exc:
                    logger.warning("%s backend error for %r: status=%s", spec.stage, query, exc.status_code)
                    return []
                except Exception as exc:
                    logger.warning("%s error for %r: %s", spec.stage, query, exc)
                    return []

            results_list = await asyncio.gather(*[_run_source(s) for s in enabled_sources])

            for r in results_list:
                all_results.append(r)

            for r in all_results:
                results = _merge_results(results, r)
        else:
            # Every parallel source is switched off. Google Books can still answer as
            # the fallback, which is the only remaining provider.
            logger.warning(
                "No parallel import search provider is enabled for %r — "
                "only the Google Books fallback is available",
                query,
            )

        if not results:
            if not _google_fallback_enabled():
                logger.warning(
                    "No results for %r and the Google Books fallback is disabled "
                    "(GOOGLE_BOOKS_IMPORT_SEARCH_ENABLED=false)",
                    query,
                )
            elif not api_key:
                logger.warning(
                    "No results for %r and GOOGLE_BOOKS_API_KEY is not set — "
                    "Google Books requires an API key for all requests. "
                    "Set GOOGLE_BOOKS_API_KEY in .env to enable the fallback.",
                    query,
                )
            else:
                logger.info("No results from any source — falling back to Google Books")
                try:
                    results = await _search_google_books(query, search_type, api_key, client)
                except SourceBackendError as exc:
                    logger.warning("Google Books backend error for %r: status=%s", query, exc.status_code)
                    results = []
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
    """Search Open Library by title or ISBN.

    Raises:
        SourceBackendError: On HTTP errors from Open Library.
    """
    if search_type == "isbn":
        params: dict = {
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
        resp = await client.get(OPEN_LIBRARY_SEARCH_URL, params=params, headers={"User-Agent": _USER_AGENT})
        logger.debug("Open Library response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Open Library HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise SourceBackendError("open_library", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        logger.warning("Open Library request failed: %s", exc)
        raise SourceBackendError("open_library") from exc

    docs = resp.json().get("docs", [])
    logger.debug("Open Library docs in response: %d", len(docs))
    candidates = [map_open_library(doc) for doc in docs if doc.get("title")]
    for c in candidates:
        logger.debug("  OL candidate: title=%r isbn=%r", c.title, c.isbn)
    return candidates


def map_open_library(doc: dict) -> BookImportCandidate:
    """Map a single Open Library search doc to BookImportCandidate."""
    # Authors: list of strings
    authors = [a for a in (doc.get("author_name") or []) if a]
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

    # Tags: first 3 subjects joined
    subjects: list[str] = doc.get("subject") or []
    tags = ", ".join(subjects[:3]) if subjects else None

    # Language: Open Library returns list[str] of ISO 639-2 codes (e.g. ["eng"])
    languages: list[str] = doc.get("language") or []
    language = _normalize_language_code(languages[0] if languages else None)

    return BookImportCandidate(
        title=doc["title"],
        subtitle=doc.get("subtitle") or None,
        author=author,
        authors=authors,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=doc.get("first_publish_year"),
        page_count=doc.get("number_of_pages_median"),
        language=language,
        tags=tags,
        source="open_library",
    )


# ── Google Books ──────────────────────────────────────────────────────────────


async def _search_google_books(
    query: str,
    search_type: str,
    api_key: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search Google Books by title or ISBN with retry logic for transient errors.

    Raises:
        SourceBackendError: On non-retryable HTTP errors.
    """
    if search_type == "isbn":
        q = f"isbn:{query}"
    else:
        q = query

    params: dict = {"q": q, "maxResults": 10}
    if api_key:
        params["key"] = api_key

    logger.debug(
        "Using Google Books API key: %s",
        _truncate_api_key(api_key),
    )

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
            raise SourceBackendError("google_books") from exc

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
        raise SourceBackendError("google_books", resp.status_code)

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
    """Fetch the full volume record to get high-res imageLinks, then probe each
    size URL (extraLarge to smallThumbnail) via a HEAD request.

    A URL is accepted when it returns HTTP 200 with either:
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
    authors: list[str] = [a for a in (vi.get("authors") or []) if a]
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

    # Tags
    categories: list[str] = vi.get("categories") or []
    tags = ", ".join(categories[:3]) if categories else None

    # Language: Google Books uses ISO 639-1 (e.g. "en")
    language = _normalize_language_code(vi.get("language"))

    return BookImportCandidate(
        title=vi["title"],
        subtitle=vi.get("subtitle") or None,
        author=author,
        authors=authors,
        isbn=isbn,
        cover_url=cover_url,
        publisher=vi.get("publisher"),
        published_year=published_year,
        page_count=vi.get("pageCount"),
        language=language,
        tags=tags,
        blurb=vi.get("description") or None,
        source="google_books",
    )


# ── Hardcover.app ──────────────────────────────────────────────────────────────


async def _search_hardcover(
    query: str,
    search_type: str,
    api_token: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search hardcover.app via GraphQL.

    For title searches, first performs a search query to obtain ISBN-13 values,
    then fetches full book metadata. For ISBN searches, fetches metadata directly.
    """
    if not api_token.strip():
        return []

    try:
        if search_type == "title":
            isbn13s = await _hardcover_search_title(query, api_token, client)
            if not isbn13s:
                return []
            return await _hardcover_fetch_books(isbn13s, api_token, client)
        else:
            try:
                isbn13 = normalize_isbn(query)
            except ValueError:
                logger.warning("hardcover invalid ISBN: %s", query)
                return []
            return await _hardcover_fetch_books([isbn13], api_token, client)
    except Exception:
        logger.exception("hardcover search failed for %r", query)
        return []


async def _hardcover_search_title(
    query: str,
    api_token: str,
    client: httpx.AsyncClient,
) -> list[str]:
    """Step 1: execute search query and extract unique ISBN-13 values."""
    variables = {"q": query}
    logger.debug("hardcover search request — url=%s query=%r", HARDCOVER_GRAPHQL_URL, query)
    try:
        resp = await client.post(
            HARDCOVER_GRAPHQL_URL,
            json={"query": HARDCOVER_SEARCH_QUERY, "variables": variables},
            headers={"Authorization": f"Bearer {api_token}"},
        )
    except httpx.HTTPError as exc:
        logger.warning("hardcover search request failed: %s", exc)
        return []

    if resp.status_code != 200:
        logger.debug("hardcover search HTTP %d: %s", resp.status_code, resp.text[:200])
        return []

    data = resp.json()
    if "errors" in data:
        logger.warning("hardcover search GraphQL errors: %s", data["errors"])
        return []

    search_results = data.get("data", {}).get("search", {}).get("results") or {}
    hits = search_results.get("hits") or []
    logger.debug("hardcover search response — found=%s hits=%d",
                 search_results.get("found"), len(hits))
    seen: set[str] = set()
    result: list[str] = []
    for hit in hits:
        document = hit.get("document") or {}
        for raw in (document.get("isbns") or []):
            if not isinstance(raw, str):
                continue
            try:
                normalized = normalize_isbn(raw)
            except ValueError:
                continue
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
            if len(result) >= 10:
                return result

    logger.debug("hardcover search extracted %d unique ISBN(s) from title search", len(result))
    return result


async def _hardcover_fetch_books(
    isbn13s: list[str],
    api_token: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Step 2: fetch full book metadata for a list of ISBN-13 values."""
    if not isbn13s:
        return []

    where = {"edition": {"isbn_13": {"_in": isbn13s}}}
    variables = {"where": where}
    logger.debug("hardcover book_mappings request — url=%s isbn13s=%s", HARDCOVER_GRAPHQL_URL, isbn13s)

    try:
        resp = await client.post(
            HARDCOVER_GRAPHQL_URL,
            json={"query": HARDCOVER_BOOK_MAPPINGS_QUERY, "variables": variables},
            headers={"Authorization": f"Bearer {api_token}"},
        )
    except httpx.HTTPError as exc:
        logger.warning("hardcover book_mappings request failed: %s", exc)
        return []

    if resp.status_code != 200:
        logger.debug("hardcover book_mappings HTTP %d: %s", resp.status_code, resp.text[:200])
        return []

    data = resp.json()
    if "errors" in data:
        logger.warning("hardcover book_mappings GraphQL errors: %s", data["errors"])
        return []

    mappings = data.get("data", {}).get("book_mappings") or []
    logger.debug("hardcover book_mappings response — %d mapping(s) returned", len(mappings))
    candidates: list[BookImportCandidate] = []
    seen: set[tuple] = set()

    for mapping in mappings:
        edition = mapping.get("edition") or {}
        candidate = map_hardcover(edition)
        if candidate is None:
            continue
        key = _hardcover_dedup_key(edition)
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        candidates.append(candidate)
        logger.debug("  HC candidate: title=%r isbn=%r cover=%r",
                     candidate.title, candidate.isbn, candidate.cover_url)

    logger.debug("hardcover book_mappings yielded %d candidate(s) after dedup", len(candidates))
    return candidates


def _hardcover_dedup_key(edition: dict) -> tuple | None:
    """Composite dedup key: (isbn_13, pages, language_code)."""
    isbn = edition.get("isbn_13")
    if not isbn:
        return None
    pages = edition.get("pages")
    lang = (edition.get("language") or {}).get("code2", "")
    return (isbn, pages, lang)


def map_hardcover(edition: dict) -> BookImportCandidate | None:
    """Map a hardcover edition node to BookImportCandidate.

    Returns None if the edition has no title.
    """
    title = edition.get("title")
    if not title:
        return None

    contributions = edition.get("contributions") or []
    authors: list[str] = []
    for c in contributions:
        author_name = (c.get("author") or {}).get("name")
        if author_name:
            authors.append(author_name)
    author = ", ".join(authors) if authors else None

    isbn = edition.get("isbn_13") or None

    image = edition.get("image") or {}
    raw_cover_url = image.get("url")
    cover_url = None
    if raw_cover_url and is_safe_cover_import_url(raw_cover_url):
        cover_url = raw_cover_url

    publisher = (edition.get("publisher") or {}).get("name") or None

    release_date = edition.get("release_date") or ""
    published_year = None
    if len(release_date) >= 4:
        try:
            published_year = int(release_date[:4])
        except ValueError:
            pass

    page_count = edition.get("pages") or None

    language = (edition.get("language") or {}).get("code2") or None
    if language:
        language = language.upper()

    taggings = edition.get("book", {}).get("taggings") or []
    tags_list = [t["tag"]["tag"] for t in taggings if t.get("tag", {}).get("tag")][:3]
    tags = ", ".join(tags_list) if tags_list else None

    blurb = edition.get("book", {}).get("description") or None

    return BookImportCandidate(
        title=title,
        subtitle=edition.get("subtitle") or None,
        author=author,
        authors=authors,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=tags,
        blurb=blurb,
        source="hardcover",
    )


# ── BnF ────────────────────────────────────────────────────────────────────────


async def _search_bnf(
    query: str,
    search_type: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search BnF catalogue general via SRU.

    Raises:
        SourceBackendError: On HTTP errors from BnF.
    """
    if search_type == "isbn":
        try:
            isbn13 = normalize_isbn(query)
        except ValueError:
            logger.warning("BnF invalid ISBN: %s", query)
            return []
        query_str = f'bib.isbn adj "{isbn13}"'
    else:
        term = _sanitize_cql_term(query)
        if not term:
            logger.debug("BnF: title query is empty after sanitizing")
            return []
        query_str = f'bib.title all "{term}" and bib.doctype adj "a"'

    params: dict = {
        "version": "1.2",
        "operation": "searchRetrieve",
        "query": query_str,
        "recordSchema": "dublincore",
        "maximumRecords": 10,
        "sortBy": "dat/sort.descending",
    }

    logger.debug("BnF request — url=%s params=%s", BNF_SRU_URL, params)

    try:
        resp = await client.get(BNF_SRU_URL, params=params, headers={"User-Agent": _USER_AGENT})
        logger.debug("BnF response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("BnF HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise SourceBackendError("bnf", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        logger.warning("BnF request failed: %s", exc)
        raise SourceBackendError("bnf") from exc

    candidates = map_bnf_response(resp.text)
    for c in candidates:
        logger.debug("  BnF candidate: title=%r isbn=%r", c.title, c.isbn)
    return candidates


def map_bnf_response(xml_text: str) -> list[BookImportCandidate]:
    """Parse BnF SRU Dublin Core XML response into BookImportCandidate list."""
    namespaces = {
        "srw": "http://www.loc.gov/zing/srw/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    try:
        # The payload comes from a remote server, so parse it with entity expansion
        # and external entity resolution disabled.
        root = SafeET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:
        logger.warning("BnF XML parse error: %s", exc)
        return []

    records = root.findall(".//oai_dc:dc", namespaces)

    # BnF answers one ISBN with every record that carries it, which includes a
    # commercial barcode stub ("Code a barres commercial : EAN ..."). The marker also
    # appears on genuine records, so it only ranks a record lower instead of dropping
    # it: within an ISBN group the richest, least barcode-ish record wins.
    best_by_key: dict[str, tuple[BookImportCandidate, bool]] = {}
    order: list[str] = []
    seen_arks: set[str] = set()

    for record in records:
        candidate = map_bnf_record(record, namespaces)
        if candidate is None:
            continue
        ark = _extract_bnf_ark(record, namespaces)
        if ark and ark in seen_arks:
            continue
        if ark:
            seen_arks.add(ark)

        key = candidate.isbn or ark or f"__record_{len(order)}"
        is_shell = _has_bnf_barcode_marker(record, namespaces)
        incumbent = best_by_key.get(key)
        if incumbent is None:
            best_by_key[key] = (candidate, is_shell)
            order.append(key)
            continue
        if not is_shell and (incumbent[1] or _bnf_record_richness(candidate) > _bnf_record_richness(incumbent[0])):
            best_by_key[key] = (candidate, is_shell)

    return [best_by_key[key][0] for key in order]


def _bnf_record_richness(candidate: BookImportCandidate) -> int:
    """Count populated fields, used to pick the better of two BnF records."""
    return sum(
        1
        for value in (
            candidate.subtitle,
            candidate.author,
            candidate.publisher,
            candidate.published_year,
            candidate.page_count,
            candidate.language,
            candidate.tags,
        )
        if value
    )


def _has_bnf_barcode_marker(record: ET.Element, namespaces: dict[str, str]) -> bool:
    """Return True when a BnF record is (or includes) the commercial barcode stub."""
    for description in record.findall("dc:description", namespaces):
        if description.text and "Code à barres commercial" in description.text:
            return True
    return False


def _extract_bnf_isbn(record: ET.Element, namespaces: dict[str, str]) -> str | None:
    """Extract the ISBN from a BnF record's dc:identifier values ('ISBN 9791020923554')."""
    for identifier in record.findall("dc:identifier", namespaces):
        text = (identifier.text or "").strip()
        match = re.search(r"ISBN\s+([0-9Xx][0-9Xx\s-]{8,}[0-9Xx])", text, re.IGNORECASE)
        if not match:
            continue
        try:
            return normalize_isbn(match.group(1))
        except ValueError:
            continue
    return None


def map_bnf_record(record: ET.Element, namespaces: dict[str, str]) -> BookImportCandidate | None:
    """Map a single BnF Dublin Core record to BookImportCandidate."""
    title_elem = record.find("dc:title", namespaces)
    if title_elem is None or not title_elem.text:
        return None

    raw_title = title_elem.text
    title, subtitle = _split_bnf_title(raw_title)

    authors: list[str] = []
    for creator in record.findall("dc:creator", namespaces):
        if creator.text:
            author = _clean_bnf_author(creator.text)
            if author:
                authors.append(author)
    for contributor in record.findall("dc:contributor", namespaces):
        if contributor.text:
            author = _clean_bnf_author(contributor.text)
            if author and author not in authors:
                authors.append(author)
    author_str = ", ".join(authors) if authors else None

    publishers = [p.text.strip() for p in record.findall("dc:publisher", namespaces) if p.text]
    publisher = _clean_bnf_publisher(publishers[0]) if publishers else None

    date_elem = record.find("dc:date", namespaces)
    published_year = None
    if date_elem is not None and date_elem.text:
        try:
            published_year = int(date_elem.text[:4])
        except (ValueError, IndexError):
            pass

    format_elem = record.find("dc:format", namespaces)
    page_count = None
    if format_elem is not None and format_elem.text:
        page_count = _parse_page_count(format_elem.text)

    languages = [l.text for l in record.findall("dc:language", namespaces) if l.text]
    language = _normalize_language_code(languages[0]) if languages else None

    subjects = [_clean_bnf_tag(s.text) for s in record.findall("dc:subject", namespaces) if s.text]
    subjects = [s for s in subjects if s]
    tags = ", ".join(subjects[:3]) if subjects else None

    return BookImportCandidate(
        title=title,
        subtitle=subtitle,
        author=author_str,
        authors=authors,
        isbn=_extract_bnf_isbn(record, namespaces),
        cover_url=None,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=tags,
        source="bnf",
    )


def _clean_bnf_publisher(raw: str) -> str:
    """Drop the BnF publication-place suffix, e.g. 'Editions Gallimard (Paris)'."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", raw).strip() or raw.strip()


def _split_bnf_title(raw_title: str) -> tuple[str, Optional[str]]:
    """Split a BnF dc:title into (title, subtitle).

    BnF conventions seen in the catalogue:
      "L'heure du Sud : ou l'invention ... (Éd. 2024)"  -> edition statement, dropped
      "Dune / Frank Herbert"                             -> statement of responsibility, dropped
      "Titre : sous-titre"                              -> real subtitle, kept
    """
    title = raw_title.strip()

    # Drop a trailing edition statement. BnF returns both accented and unaccented
    # forms, e.g. "(Ed. 2024)" and "(Éd. 2024)".
    title = re.sub(
        r"\s*\((?:[ÉEeé]d\.?|[ÉEeé]dition)\s*[^()]*\)\s*$",
        "",
        title,
    ).strip()

    # Drop a trailing statement of responsibility after " / ".
    if " / " in title:
        title = title.split(" / ", 1)[0].strip()

    if " : " in title:
        head, tail = title.split(" : ", 1)
        subtitle = tail.split(" / ", 1)[0].strip() if " / " in tail else tail.strip()
        # The edition statement may sit after the subtitle rather than the whole title.
        subtitle = re.sub(
            r"\s*\((?:[ÉEeé]d\.?|[ÉEeé]dition)\s*[^()]*\)\s*$",
            "",
            subtitle,
        ).strip()
        return head.strip(), subtitle or None

    return title, None


# BnF subject headings use " -- " for subdivisions ("Relations internationales --
# 2001-...."). Keep the top-level heading only.
_BNF_SUBDIVISION_RE = re.compile(r"\s+--\s+.*$")


def _clean_bnf_tag(tag: str) -> str:
    """Strip the subdivision suffix from a single BnF subject heading."""
    return _BNF_SUBDIVISION_RE.sub("", tag).strip() or tag.strip()


def _sanitize_cql_term(value: str) -> str:
    """Make a user query safe to interpolate inside a quoted CQL string.

    A stray double quote would otherwise terminate the CQL string early; BnF answers
    such a query with a diagnostic document and zero records instead of an error, so
    the breakage would be silent.
    """
    cleaned = value.replace('"', " ").replace("\\", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


# Role terms BnF appends after a personal name (UNIMARC 7xx role codes rendered in
# French). Matching a known vocabulary keeps real names such as "Ursula K. Le Guin"
# intact, which a generic "strip everything after a period" rule would mangle.
_BNF_ROLE_RE = re.compile(
    r"\.\s*(?:auteur|editeur|éditeur|traducteur|postfacier|préfacier|prefacier|"
    r"illustrateur|directeur de publication|photographe|compilateur|annotateur|"
    r"correcteur|dessinateur|graveur|interviewer|prologue|epilogue|épilogue|"
    r"preface|préface|enregistrement|editing|revue de|de)\b.*$",
    re.IGNORECASE,
)


def _clean_bnf_author(raw: str) -> str:
    """Strip BnF role suffixes from a creator/contributor string.

    Handles "Badie, Bertrand (1950-....). Éditeur scientifique" and
    "Labica, Thierry. Postfacier" down to the bare name.
    """
    author = raw.strip()

    # Life dates first: "Name (1900-1980)" or "Name (1950-.... ; journaliste)".
    author = re.sub(r"\s*\((?:\d{4}|-{3})[^)]*\)", "", author).strip()

    # Then a trailing role phrase: "Name. Postfacier".
    author = _BNF_ROLE_RE.sub("", author).strip()

    return author.rstrip(".").strip() or raw.strip()


def _extract_bnf_ark(record: ET.Element, namespaces: dict[str, str]) -> str | None:
    """Extract BnF ARK identifier from a record."""
    for identifier in record.findall("dc:identifier", namespaces):
        if identifier.text and "ark:/" in identifier.text:
            return identifier.text.strip()
    return None


# ── Inventaire.io ───────────────────────────────────────────────────────────────

# Claims pulled along with the edition in the single by-uris request:
#   P629 -> the work, P50 -> authors on that work, P123 -> publisher.
# Each relative is returned as a full entity with resolved labels.
INVENTAIRE_RELATIVES: tuple[str, ...] = ("wdt:P629", "wdt:P50", "wdt:P123")

_LANG_PREFERENCE: tuple[str, ...] = ("en", "fr", "de", "es", "it")


async def _search_inventaire(
    query: str,
    search_type: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search inventaire.io by ISBN via the entities API.

    Inventaire is ISBN-only: it has no usable title-search route.

    Raises:
        SourceBackendError: On HTTP errors from inventaire.io.
    """
    if search_type != "isbn":
        logger.debug("Inventaire: skipping title search (ISBN-only provider)")
        return []

    try:
        isbn13 = normalize_isbn(query)
    except ValueError:
        logger.warning("Inventaire invalid ISBN: %s", query)
        return []

    # relatives must be repeated query params; a comma-joined value returns HTTP 400.
    params: list[tuple[str, str]] = [("uris", f"isbn:{isbn13}")]
    params += [("relatives", rel) for rel in INVENTAIRE_RELATIVES]
    params.append(("lang", "en"))

    logger.debug("Inventaire request — url=%s isbn=%s", INVENTAIRE_ENTITIES_URL, isbn13)

    try:
        resp = await client.get(INVENTAIRE_ENTITIES_URL, params=params, headers={"User-Agent": _USER_AGENT})
        logger.debug("Inventaire response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Inventaire HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise SourceBackendError("inventaire", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        logger.warning("Inventaire request failed: %s", exc)
        raise SourceBackendError("inventaire") from exc

    candidates = map_inventaire_response(resp.json())
    for c in candidates:
        logger.debug("  Inventaire candidate: title=%r author=%r isbn=%r cover=%r",
                     c.title, c.author, c.isbn, c.cover_url)
    return candidates


def map_inventaire_response(data: dict) -> list[BookImportCandidate]:
    """Parse an inventaire.io by-uris response into a BookImportCandidate list.

    The response is ``{"entities": {uri: entity}, "redirects": {"isbn:...": uri}}``.
    Every claim value is a plain string; the ISBN redirect points at the edition.
    """
    entities: dict[str, dict] = data.get("entities") or {}
    if not entities:
        return []

    edition_uri = _find_inventaire_edition_uri(data.get("redirects") or {}, entities)
    if edition_uri is None:
        return []

    edition = entities[edition_uri]
    candidate = map_inventaire_entity(edition, entities, entities[edition_uri].get("labels") or {})
    if candidate is None:
        return []
    if not candidate.isbn:
        candidate = candidate.model_copy(update={"isbn": _isbn_from_uri(edition_uri)})
    return [candidate]


def _find_inventaire_edition_uri(redirects: dict[str, str], entities: dict[str, dict]) -> str | None:
    """Return the URI of the edition entity in an inventaire.io response."""
    for uri, target in redirects.items():
        if uri.startswith("isbn:") and target in entities:
            return target
    # Fall back to any entity that actually is an edition.
    for uri, entity in entities.items():
        if entity.get("type") == "edition":
            return uri
    return None


def _isbn_from_uri(uri: str) -> str | None:
    """Return the ISBN carried by an ``isbn:<value>`` URI, normalized.

    Returns None when the value is not a valid ISBN, so a malformed identifier is
    never persisted.
    """
    if not uri.startswith("isbn:"):
        return None
    raw = uri[len("isbn:"):]
    try:
        return normalize_isbn(raw)
    except ValueError:
        logger.debug("Inventaire returned a non-ISBN identifier: %r", raw)
        return None


def map_inventaire_entity(
    edition: dict,
    entities: dict[str, dict],
    labels: dict[str, str] | None = None,
) -> BookImportCandidate | None:
    """Map an inventaire.io edition entity to BookImportCandidate."""
    claims: dict[str, list[str]] = edition.get("claims") or {}

    title = _inventaire_claim(claims, "wdt:P1476")
    if not title:
        title = _inventaire_label(labels or {})
    if not title:
        return None
    subtitle = _inventaire_claim(claims, "wdt:P1680")

    isbn: str | None = None
    for raw in _inventaire_claims(claims, "wdt:P212") + _inventaire_claims(claims, "wdt:P957"):
        try:
            isbn = normalize_isbn(raw)
            break
        except ValueError:
            continue

    published_year = _inventaire_year(_inventaire_claim(claims, "wdt:P577"))
    page_count = _inventaire_int(_inventaire_claim(claims, "wdt:P1104"))

    language = _normalize_language_code(edition.get("originalLang") or None)

    cover_url = _inventaire_cover(edition, claims)

    authors = _inventaire_authors(claims, entities)
    author = ", ".join(authors) if authors else None

    publisher = _inventaire_publisher(claims, entities)

    return BookImportCandidate(
        title=title,
        subtitle=subtitle,
        author=author,
        authors=authors,
        isbn=isbn,
        cover_url=cover_url,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=None,
        source="inventaire",
    )


def _inventaire_claims(claims: dict[str, list[str]], claim_id: str) -> list[str]:
    """Return the string values of a claim, tolerating legacy dict-shaped values."""
    values: list[str] = []
    for raw in claims.get(claim_id) or []:
        if isinstance(raw, str) and raw:
            values.append(raw)
        elif isinstance(raw, dict):
            value = raw.get("value")
            if isinstance(value, str) and value:
                values.append(value)
    return values


def _inventaire_claim(claims: dict[str, list[str]], claim_id: str) -> str | None:
    """Return the first string value of a claim."""
    values = _inventaire_claims(claims, claim_id)
    return values[0] if values else None


def _inventaire_label(labels: dict[str, str]) -> str | None:
    """Pick a label in the reader's likely language, ignoring generated ones."""
    for key in _LANG_PREFERENCE:
        value = labels.get(key)
        if value:
            return value
    return None


def _inventaire_year(raw: str | None) -> int | None:
    """Extract the year from a Wikidata date value such as '2024-03-01'."""
    if not raw:
        return None
    match = re.match(r"^(-?\d{1,4})", raw.strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _inventaire_int(raw: str | None) -> int | None:
    """Parse a numeric claim value such as a page count."""
    if not raw:
        return None
    match = re.search(r"\d+", raw)
    if not match:
        return None
    return int(match.group(0))


def _inventaire_cover(edition: dict, claims: dict[str, list[str]]) -> str | None:
    """Build the absolute cover URL from the image hash, if one exists."""
    cover_hash = _inventaire_claim(claims, "invp:P2")
    if not cover_hash:
        image_url = (edition.get("image") or {}).get("url") or ""
        cover_hash = image_url.rsplit("/", 1)[-1] if image_url else ""
    if not cover_hash:
        return None
    cover_url = f"{INVENTAIRE_COVER_BASE_URL}/{cover_hash}"
    return cover_url if is_safe_cover_import_url(cover_url) else None


def _inventaire_authors(claims: dict[str, list[str]], entities: dict[str, dict]) -> list[str]:
    """Resolve author labels from the work entity referenced by the edition.

    Native inventaire works often carry no P50, so the edition's own P50 is used as a
    fallback when the work yields nothing.
    """
    work_uri = _inventaire_claim(claims, "wdt:P629")
    work = entities.get(work_uri) if work_uri else None

    authors = _inventaire_author_labels((work or {}).get("claims") or {}, entities)
    if not authors:
        authors = _inventaire_author_labels(claims, entities)
    return authors


def _inventaire_author_labels(claims: dict[str, list[str]], entities: dict[str, dict]) -> list[str]:
    """Resolve P50 author URIs into display labels."""
    authors: list[str] = []
    for author_uri in _inventaire_claims(claims, "wdt:P50"):
        entity = entities.get(author_uri)
        label = _inventaire_label((entity or {}).get("labels") or {})
        if label and label not in authors:
            authors.append(label)
    return authors


def _inventaire_publisher(claims: dict[str, list[str]], entities: dict[str, dict]) -> str | None:
    """Resolve the publisher label from the edition's P123 relative."""
    publisher_uri = _inventaire_claim(claims, "wdt:P123")
    if not publisher_uri:
        return None
    entity = entities.get(publisher_uri)
    if not entity:
        return None
    return _inventaire_label(entity.get("labels") or {})


# ── Library of Congress ────────────────────────────────────────────────────────


async def _search_loc(
    query: str,
    search_type: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search Library of Congress via SRU.

    Raises:
        SourceBackendError: On HTTP errors from LoC.
    """
    if search_type == "isbn":
        try:
            isbn13 = normalize_isbn(query)
        except ValueError:
            logger.warning("LoC invalid ISBN: %s", query)
            return []
        query_str = f"bath.isbn={isbn13}"
    else:
        term = _sanitize_cql_term(query)
        if not term:
            logger.debug("LoC: title query is empty after sanitizing")
            return []
        query_str = f"bath.title={term}"

    params: dict = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": query_str,
        "recordSchema": "mods",
        "maximumRecords": 10,
    }

    logger.debug("LoC request — url=%s params=%s", LOC_SRU_URL, params)

    try:
        # LoC is reached over plain HTTP on port 210, which many firewalls drop rather
        # than refuse. A shorter timeout keeps a blocked LoC from stalling the search.
        resp = await client.get(
            LOC_SRU_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=_LOC_TIMEOUT_SECONDS,
        )
        logger.debug("LoC response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("LoC HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise SourceBackendError("library_of_congress", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        logger.warning("LoC request failed: %s", exc)
        raise SourceBackendError("library_of_congress") from exc

    candidates = map_loc_response(resp.text)
    for c in candidates:
        logger.debug("  LoC candidate: title=%r isbn=%r", c.title, c.isbn)
    return candidates


def map_loc_response(xml_text: str) -> list[BookImportCandidate]:
    """Parse LoC SRU MODS XML response into BookImportCandidate list."""
    namespaces = {
        "srw": "http://www.loc.gov/zing/srw/",
        "mods": "http://www.loc.gov/mods/v3",
    }

    try:
        # The payload comes from a remote server, so parse it with entity expansion
        # and external entity resolution disabled.
        root = SafeET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:
        logger.warning("LoC XML parse error: %s", exc)
        return []

    records = root.findall(".//mods:mods", namespaces)
    candidates: list[BookImportCandidate] = []

    for record in records:
        candidate = map_loc_record(record, namespaces)
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def map_loc_record(record: ET.Element, namespaces: dict[str, str]) -> BookImportCandidate | None:
    """Map a single LoC MODS record to BookImportCandidate."""
    title_info = record.find("mods:titleInfo", namespaces)
    if title_info is None:
        return None

    title_elem = title_info.find("mods:title", namespaces)
    if title_elem is None or not title_elem.text:
        return None

    title = title_elem.text.strip()

    subtitle_elem = title_info.find("mods:subTitle", namespaces)
    subtitle = subtitle_elem.text.strip() if subtitle_elem is not None and subtitle_elem.text else None

    authors: list[str] = []
    for name in record.findall("mods:name", namespaces):
        # Only personal names are book authors; corporate names would be the publisher.
        name_type = name.get("type", "")
        if name_type and name_type != "personal":
            continue
        name_part = name.find("mods:namePart", namespaces)
        if name_part is not None and name_part.text:
            author = _reverse_loc_author(name_part.text.strip())
            if author and author not in authors:
                authors.append(author)
    author_str = ", ".join(authors) if authors else None

    isbn = _extract_loc_isbn(record, namespaces)

    origin_info = record.find("mods:originInfo", namespaces)
    publisher = None
    published_year = None
    if origin_info is not None:
        publisher_elem = origin_info.find("mods:publisher", namespaces)
        if publisher_elem is not None and publisher_elem.text:
            publisher = publisher_elem.text.strip()

        date_elem = origin_info.find("mods:dateIssued", namespaces)
        if date_elem is not None and date_elem.text:
            try:
                published_year = int(date_elem.text[:4])
            except (ValueError, IndexError):
                pass

    language = None
    for lang in record.findall("mods:language", namespaces):
        term = lang.find("mods:languageTerm", namespaces)
        if term is not None and term.text:
            language = _normalize_language_code(term.text.strip())
            break

    page_count = None
    physical_desc = record.find("mods:physicalDescription", namespaces)
    if physical_desc is not None:
        extent = physical_desc.find("mods:extent", namespaces)
        if extent is not None and extent.text:
            page_count = _parse_page_count(extent.text)

    tags = None
    # MODS nests topics inside <subject>, so search descendants rather than direct children.
    topics = [t.text for t in record.findall(".//mods:topic", namespaces) if t.text]
    if topics:
        tags = ", ".join(topics[:3])

    return BookImportCandidate(
        title=title,
        subtitle=subtitle,
        author=author_str,
        authors=authors,
        isbn=isbn,
        cover_url=None,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=tags,
        source="library_of_congress",
    )


def _extract_loc_isbn(record: ET.Element, namespaces: dict[str, str]) -> str | None:
    """Extract an ISBN from MODS identifier elements, preferring type='isbn'."""
    fallbacks: list[str] = []
    for identifier in record.findall("mods:identifier", namespaces):
        text = (identifier.text or "").strip()
        if not text or not re.fullmatch(r"[0-9Xx][0-9Xx\s-]{8,}[0-9Xx]", text):
            continue
        try:
            normalized = normalize_isbn(text)
        except ValueError:
            continue
        if identifier.get("type") == "isbn":
            return normalized
        fallbacks.append(normalized)
    return fallbacks[0] if fallbacks else None


def _reverse_loc_author(raw: str) -> str:
    """Reverse LoC's 'LastName, FirstName' form into 'FirstName LastName'.

    Real MODS namePart values carry trailing separators in both forms:
    "Herbert, Frank." (abbreviation period) and "Horydczak, Theodor," (list comma).
    Both must be stripped before the name is reversed.
    """
    name = raw.strip().rstrip(".,").strip()
    if ", " in name:
        last, first = name.split(", ", 1)
        reversed_name = f"{first.strip().rstrip('.,')} {last.strip().rstrip('.,')}".strip()
        return reversed_name or name
    return name or raw.strip()


# ── Deutsche Nationalbibliothek (DNB) ─────────────────────────────────────────

# The DNB SRU envelope puts the SRU namespace on the root as the default namespace,
# and each MARC21 record declares its own default namespace, so both have to be
# named explicitly to select them.
async def _search_dnb(
    query: str,
    search_type: str,
    client: httpx.AsyncClient,
) -> list[BookImportCandidate]:
    """Search the German National Library via its SRU interface.

    Raises:
        SourceBackendError: On HTTP errors from the DNB.
    """
    if search_type == "isbn":
        try:
            isbn13 = normalize_isbn(query)
        except ValueError:
            logger.warning("DNB invalid ISBN: %s", query)
            return []
        query_str = f"num={isbn13}"
    else:
        term = _sanitize_cql_term(query)
        if not term:
            logger.debug("DNB: title query is empty after sanitizing")
            return []
        # Quoted so a title containing "and" or "or" is not read as a CQL operator.
        query_str = f'tit="{term}"'

    params: dict = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": query_str,
        "recordSchema": "MARC21-xml",
        "maximumRecords": 10,
    }

    logger.debug("DNB request — url=%s params=%s", DNB_SRU_URL, params)

    try:
        resp = await client.get(DNB_SRU_URL, params=params, headers={"User-Agent": _USER_AGENT})
        logger.debug("DNB response — status=%d body_size=%d bytes",
                     resp.status_code, len(resp.content))
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("DNB HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise SourceBackendError("dnb", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        logger.warning("DNB request failed: %s", exc)
        raise SourceBackendError("dnb") from exc

    candidates = map_dnb_response(resp.text)
    for c in candidates:
        logger.debug("  DNB candidate: title=%r isbn=%r", c.title, c.isbn)
    return candidates


def map_dnb_response(xml_text: str) -> list[BookImportCandidate]:
    """Parse a DNB SRU MARC21 response into a BookImportCandidate list."""
    try:
        # The payload comes from a remote server, so parse it with entity expansion and
        # external entity resolution disabled.
        root = SafeET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:
        logger.warning("DNB XML parse error: %s", exc)
        return []

    candidates: list[BookImportCandidate] = []
    for record in root.findall(".//srw:recordData/marc:record", _DNB_NAMESPACES):
        candidate = map_dnb_record(record)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def map_dnb_record(record: ET.Element) -> BookImportCandidate | None:
    """Map a single DNB MARC21 record to a BookImportCandidate."""
    title, subtitle = _dnb_title(record)
    if not title:
        return None

    # 264 second indicator 1 is the publication statement; 4 is the copyright statement,
    # which carries a different (often reprint) date and must not be used as the
    # publication year. Older records use 260, which has no publication indicator.
    publication = None
    for tag in ("264", "260"):
        for field in record.findall(f"marc:datafield[@tag='{tag}']", _DNB_NAMESPACES):
            # A missing indicator is "no information", which in practice is a publication
            # statement; an explicit " " is accepted as a last resort.
            ind2 = field.get("ind2")
            if tag == "264" and ind2 not in ("1", " ", None):
                continue
            publication = field
            break
        if publication is not None:
            break

    publisher = None
    if publication is not None:
        publisher = _strip_dnb_brackets(_dnb_first(publication, "b"))
    published_year = _dnb_publication_year(
        _dnb_first(publication, "c") if publication is not None else None
    )

    page_count = None
    extent = record.find("marc:datafield[@tag='300']", _DNB_NAMESPACES)
    extent_text = _dnb_first(extent, "a") if extent is not None else None
    if extent_text:
        page_count = _parse_dnb_page_count(extent_text)

    # 041$a is the language of the text; $h names the language it was translated from.
    language = None
    language_field = record.find("marc:datafield[@tag='041']", _DNB_NAMESPACES)
    if language_field is not None:
        for value in _dnb_subfields(language_field).get("a", []):
            language = _normalize_language_code(value.split()[0] if value else None)
            if language:
                break
    if not language:
        fixed = record.find("marc:controlfield[@tag='008']", _DNB_NAMESPACES)
        if fixed is not None and fixed.text and len(fixed.text) >= 38:
            language = _normalize_language_code(fixed.text[35:38])

    authors = _dnb_authors(record)
    blurb_field = record.find("marc:datafield[@tag='520']", _DNB_NAMESPACES)

    # The DNB SRU endpoint serves no cover images, so there is nothing to set here.
    return BookImportCandidate(
        title=title,
        subtitle=subtitle,
        author=authors[0] if authors else None,
        authors=authors or None,
        isbn=_extract_dnb_isbn(record),
        cover_url=None,
        publisher=publisher,
        published_year=published_year,
        page_count=page_count,
        language=language,
        tags=_dnb_subjects(record),
        blurb=_dnb_first(blurb_field, "a") if blurb_field is not None else None,
        source="dnb",
    )


_DNB_NAMESPACES: dict[str, str] = {
    "srw": "http://www.loc.gov/zing/srw/",
    "marc": "http://www.loc.gov/MARC21/slim",
}

# DNB records wrap non-sorting characters in U+0098 (string start) and U+009C
# (string terminator) instead of using the MARC nonfiling indicator. Leaving them in
# would show up in the title as stray control characters. The whole C1 range is
# stripped so a stray marker anywhere in a subfield is handled, not just the
# documented pair.
_DNB_NONFILING_RE = re.compile("[\u0098-\u009f]")

# MARC relator term codes for "this person wrote the book". A 1XX field that codes any
# other role (editor, translator, illustrator) is a contributor, not the author.
_DNB_AUTHOR_ROLES: frozenset[str] = frozenset({"aut", "cre"})

# Trailing punctuation on a catalogued name: the period in "Mann, Thomas." is noise, but
# the one in "Karl R." is a real initial. Only drop it when the final word is long enough
# not to be an initial.
_DNB_TRAILING_PERIOD_RE = re.compile(r"(?<=\S)\.\s*$")


def _drop_dnb_trailing_period(text: str) -> str:
    """Remove cataloguing noise from the forename half of an inverted name.

    Applied only to the given side of a "Surname, Forename." entry, where a trailing
    period is inversion punctuation rather than part of the name. A single-letter token
    is an initial and keeps its period ("Karl R." -> "Karl R. Popper"); anything longer is
    a full forename whose period is cataloguing noise ("Thomas." -> "Thomas Mann").

    Never applied to a name that is not inverted: "Dr.", "Prof.", "MSc." and "BSc." are
    titles and abbreviations, not inversion artifacts, and stripping them would mangle the
    name.
    """
    if not text.endswith("."):
        return text
    if len(text.rsplit(" ", 1)[-1].rstrip(".")) <= 1:
        return text
    return _DNB_TRAILING_PERIOD_RE.sub("", text)


# "1184 Seiten", "1.184 Seiten", "926 pages", "XXXIX, 601 S.". The number is either a
# plain digit run or digit groups joined by a single grouping separator, and must not sit
# directly behind another digit or separator. Three consequences, all deliberate:
#   * no lazy quantifier next to \s*, so a long non-matching run cannot backtrack
#     quadratically the way `[0-9][0-9.,\u00a0 ]*?` did;
#   * a group is exactly three digits, so German "1.184" stays 1184 while a decimal
#     "1.5" or a short group "1,23" is rejected instead of yielding a wrong page count;
#   * the lookbehind stops the tail of "1.5" being read as a count of 5.
# Note this provider-local parser is deliberately separate from the shared
# `_parse_page_count`, which handles the "265 p." style used by the other sources.
_DNB_EXTENT_RE = re.compile(
    r"(?<![0-9.,\u00a0])"
    r"((?:[0-9]{1,3}(?:[.,\u00a0 ][0-9]{3})+|[0-9]{1,15}))"
    r"\s*(?:Seiten?|pages?|sidor|p\.|S\.)",
    re.IGNORECASE,
)


def _strip_dnb_markers(text: str) -> str:
    """Remove DNB non-sorting control markers and collapse the whitespace they leave."""
    return re.sub(r"\s+", " ", _DNB_NONFILING_RE.sub("", text)).strip()


def _dnb_subfields(field: ET.Element) -> dict[str, list[str]]:
    """Group a MARC21 datafield's subfields by code, in document order."""
    grouped: dict[str, list[str]] = {}
    for subfield in field.findall("marc:subfield", _DNB_NAMESPACES):
        text = _strip_dnb_markers(subfield.text or "")
        if text:
            grouped.setdefault(subfield.get("code", ""), []).append(text)
    return grouped


def _dnb_first(field: ET.Element, *codes: str) -> str | None:
    """Return the first non-empty subfield value among the given codes.

    The field must not be None: every caller has already checked whether the MARC field
    is present before reading a subfield from it.
    """
    grouped = _dnb_subfields(field)
    for code in codes:
        for value in grouped.get(code, []):
            if value:
                return value
    return None


def _strip_dnb_brackets(value: str | None) -> str | None:
    """Unwrap a catalogued value the DNB flagged as supplied rather than transcribed.

    "[2026]" and "[Lisboa]" mean the cataloguer inferred these, and the brackets should
    not reach the user. Applied to the publisher and the publication year.

    Deliberately NOT applied to the title: the Library of Congress documents titles such
    as `24500$a[Man smoking at window]`, where the brackets are part of the title itself.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    return cleaned or None


def _reverse_dnb_name(raw: str) -> str:
    """Turn a catalogued "Surname, Forename" into "Forename Surname".

    The DNB indexes personal names inverted (MARC 1XX first indicator 1), which is the
    one part of the format that is pure cataloguing convention rather than data.
    """
    name = _strip_dnb_markers(raw).strip(" ,;")
    if "," not in name:
        # Not an inverted name, so there is no inversion punctuation to remove. Titles and
        # abbreviations such as "Dr." or "MSc." must survive intact.
        return name
    surname, _, given = name.partition(",")
    # strip(" ,;") above guarantees neither side is empty once trimmed again here.
    surname = surname.strip().rstrip(".").strip()
    given = _drop_dnb_trailing_period(given.strip()).strip()
    return f"{given} {surname}".strip() or name


def _parse_dnb_page_count(text: str) -> Optional[int]:
    """Pull the page count out of a DNB 300$a extent statement."""
    match = _DNB_EXTENT_RE.search(_strip_dnb_markers(text))
    if not match:
        return None
    # The pattern only ever captures digits and grouping separators, so the strip below
    # always leaves a plain digit string.
    count = int(re.sub(r"[.,\u00a0 ]", "", match.group(1)))
    return count if count > 0 else None


def _dnb_publication_year(date: str | None) -> Optional[int]:
    """Extract a four-digit publication year, tolerating catalogued ranges and suffixes."""
    if not date:
        return None
    match = re.search(r"(\d{4})", _strip_dnb_brackets(date) or "")
    if not match:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2999 else None


def _dnb_authors(record: ET.Element) -> list[str]:
    """Collect book authors from MARC 1XX and 700 fields, main entry first.

    The DNB puts the lead author in 1XX and co-authors in 700 added entries. Every 700
    it records carries a relator code, and those codes are mostly *not* authorship (edt,
    trl, ill and art outnumber aut several times over), so a 700 is only taken when it
    explicitly codes an author. The role is read from $4 alone: where $e is present it
    simply restates $4 in German (edt/Herausgeber, aut/Verfasser).
    """
    authors: list[str] = []

    def _add(field: ET.Element, *, strict: bool) -> None:
        grouped = _dnb_subfields(field)
        roles = {role.lower() for role in grouped.get("4", [])}
        # strict: only an explicit author relator qualifies. Loose (1XX main entry):
        # an uncoded field is still the record's main entry, so accept it.
        if roles and not (roles & _DNB_AUTHOR_ROLES):
            return
        if strict and not roles:
            return
        raw = grouped.get("a", [None])[0]
        if not raw:
            return
        name = _reverse_dnb_name(raw)
        if name and name not in authors:
            authors.append(name)

    # Main entry first: a personal name, else a corporate or meeting main entry.
    for tag in ("100", "110", "111"):
        for field in record.findall(f"marc:datafield[@tag='{tag}']", _DNB_NAMESPACES):
            _add(field, strict=False)
        if authors:
            break

    # Then author-coded co-authors from the added entries.
    for field in record.findall("marc:datafield[@tag='700']", _DNB_NAMESPACES):
        _add(field, strict=True)

    return authors


def _dnb_title(record: ET.Element) -> tuple[str | None, str | None]:
    """Return the title and subtitle from the record's MARC 245 field.

    245 is non-repeating and its first indicator only records whether a title added
    entry is made (0 or 1), not which of several titles is "main", so there is nothing to
    rank: the first field carrying a $a is the title. The loop exists only so a record
    that somehow carries several 245 fields still yields the first usable title rather
    than being dropped for having a title-less 245 first.
    """
    for field in record.findall("marc:datafield[@tag='245']", _DNB_NAMESPACES):
        title = _dnb_first(field, "a")
        if title:
            return title, _dnb_first(field, "b")
    return None, None


def _extract_dnb_isbn(record: ET.Element) -> Optional[str]:
    """Return the record's ISBN, normalized to ISBN-13.

    A 020 carrying a $q qualifier is dropped whole: the DNB uses that field to record a
    misprinted ISBN together with a note saying it is wrong and no correct value could be
    determined, and $9 then normalizes the bad value. Importing that number would attach
    the book to an ISBN that identifies something else.

    Every value goes through normalize_isbn and unparseable ones are discarded, so a
    candidate never carries an ISBN that could not be looked up again later.
    """
    normalized: list[str] = []
    for field in record.findall("marc:datafield[@tag='020']", _DNB_NAMESPACES):
        grouped = _dnb_subfields(field)
        if grouped.get("q"):
            continue
        for code in ("a", "9"):
            for value in grouped.get(code, []):
                try:
                    normalized.append(normalize_isbn(value))
                except ValueError:
                    continue
    # normalize_isbn always returns ISBN-13, so the first usable value is the answer.
    return normalized[0] if normalized else None


def _dnb_subjects(record: ET.Element) -> Optional[str]:
    """Collect subject headings from MARC 650 fields.

    689 is deliberately ignored: in DNB records it restates the same headings as 650 in a
    topical form, so including it would double every tag. The list is capped at three to
    match the BnF and Library of Congress providers, since tags render as a display field.
    """
    subjects: list[str] = []
    for field in record.findall("marc:datafield[@tag='650']", _DNB_NAMESPACES):
        value = _dnb_first(field, "a")
        if value and value not in subjects:
            subjects.append(value)
    return ", ".join(subjects[:3]) if subjects else None


# ── Merge / Deduplicate ───────────────────────────────────────────────────────


def _merge_results(*lists: list[BookImportCandidate]) -> list[BookImportCandidate]:
    """Merge multiple candidate lists, preserving every candidate in input order.

    The frontend is responsible for grouping variants that represent the same
    book (e.g. by ISBN) and letting the user pick the best record. A user can
    only own one book per exact ISBN string, so keeping all provider-specific
    records lets the user compare data quality before importing.
    """
    merged: list[BookImportCandidate] = []
    for lst in lists:
        merged.extend(lst)
    return merged


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_page_count(text: str) -> Optional[int]:
    """Extract page count from a format string like '1 vol. (265 p.) ; 20 cm' or '412 p. ; 22 cm.'.

    Handles the English/BnF/LoC conventions only. The DNB has its own
    `_parse_dnb_page_count` because its extent statements are localized
    ("1184 Seiten", "1.184 Seiten", "416 sidor") and group thousands differently.
    """
    # Try parenthesized format first: (265 p.)
    match = re.search(r"\(([\d,\s]+)\s*p\.\)", text)
    if match:
        try:
            return int(match.group(1).replace(",", "").replace(" ", ""))
        except ValueError:
            pass
    # Try plain format: 412 p. (or 1,234 p.)
    match = re.search(r"([\d,]+)\s*p\.", text)
    if match:
        try:
            return int(match.group(1).replace(",", "").replace(" ", ""))
        except ValueError:
            pass
    return None


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
    """Convert an ISO language code (ISO 639-1 or 639-2) to uppercase ISO 639-1.

    Returns None if the code cannot be resolved.
    """
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
