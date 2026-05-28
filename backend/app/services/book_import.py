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
from app.services.cover_import import is_safe_cover_import_url
from app.services.isbn_utils import normalize_isbn

logger = logging.getLogger(__name__)

OPEN_LIBRARY_SEARCH_URL: str = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL: str = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

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

    def __init__(self, source: Literal["open_library", "google_books"], status_code: int | None = None) -> None:
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
      open_library  / status=searching
      open_library  / status=done, count=int
      open_library  / status=error, reason=str
      hardcover     / status=searching
      hardcover     / status=done, count=int
      hardcover     / status=skipped, reason=str
      hardcover     / status=error, reason=str
      google_books  / status=searching
      google_books  / status=done, count=int
      google_books  / status=skipped, reason=str
      google_books  / status=error, reason=str
      complete      / results=list[dict]
      error         / message=str

    Args:
        query: Search query string.
        search_type: ``"title"`` or ``"isbn"``.
        api_key: Google Books API key (optional).
        hardcover_api_token: Hardcover.app API token (optional).
        mode: ``"auto"`` (OL + HC, fallback to GB) or ``"google_only"``.
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
            if not api_key:
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
            ol_events: list[dict] = []
            hc_events: list[dict] = []
            ol_results: list[BookImportCandidate] = []
            hc_results: list[BookImportCandidate] = []

            yield {"stage": "open_library", "status": "searching"}
            if hardcover_api_token.strip():
                yield {"stage": "hardcover", "status": "searching"}

            async def _run_ol() -> None:
                nonlocal ol_results, ol_events
                try:
                    r = await _search_open_library(query, search_type, client)
                    ol_results = r
                    ol_events.append({"stage": "open_library", "status": "done", "count": len(r)})
                except SourceBackendError as exc:
                    ol_events.append({"stage": "open_library", "status": "error", "reason": "backend_error"})

            async def _run_hc() -> None:
                nonlocal hc_results, hc_events
                if not hardcover_api_token.strip():
                    hc_events.append({"stage": "hardcover", "status": "skipped", "reason": "no_api_token"})
                    return
                try:
                    r = await _search_hardcover(query, search_type, hardcover_api_token, client)
                    hc_results = r
                    hc_events.append({"stage": "hardcover", "status": "done", "count": len(r)})
                except Exception:
                    logger.exception("hardcover search error")
                    hc_events.append({"stage": "hardcover", "status": "error", "reason": "backend_error"})

            await asyncio.gather(_run_ol(), _run_hc())

            for e in ol_events:
                yield e
            for e in hc_events:
                yield e

            results = _merge_and_deduplicate(ol_results, hc_results)

            if not results:
                if not api_key:
                    logger.warning("No results for %r and GOOGLE_BOOKS_API_KEY is not set", query)
                    yield {"stage": "google_books", "status": "skipped", "reason": "no_api_key"}
                else:
                    logger.info("No OL/HC results — falling back to Google Books")
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
    """Search Open Library in parallel with Hardcover; fall back to Google Books if both empty.

    Args:
        query: Search query string.
        search_type: ``"title"`` or ``"isbn"``.
        api_key: Google Books API key (optional).
        hardcover_api_token: Hardcover.app API token (optional).
        http_client: Reusable httpx client (created internally if omitted).

    Returns:
        A deduplicated list of BookImportCandidate objects.
    """
    logger.debug("search() called — query=%r search_type=%r has_api_key=%s has_hc_token=%s",
                 query, search_type, bool(api_key), bool(hardcover_api_token))

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": _USER_AGENT},
    )

    try:
        tasks = [_search_open_library(query, search_type, client)]
        if hardcover_api_token.strip():
            tasks.append(_search_hardcover(query, search_type, hardcover_api_token, client))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        ol_results = results_list[0] if not isinstance(results_list[0], Exception) else []
        if isinstance(results_list[0], SourceBackendError):
            logger.warning("Open Library backend error for %r: status=%s", query, results_list[0].status_code)
        elif isinstance(results_list[0], Exception):
            logger.warning("Open Library error for %r: %s", query, results_list[0])

        hc_results: list[BookImportCandidate] = []
        if len(results_list) > 1:
            if not isinstance(results_list[1], Exception):
                hc_results = results_list[1]
            else:
                logger.warning("Hardcover error for %r: %s", query, results_list[1])

        logger.info("Open Library returned %d result(s) for %r", len(ol_results), query)
        logger.info("Hardcover returned %d result(s) for %r", len(hc_results), query)

        results = _merge_and_deduplicate(ol_results, hc_results)

        if not results:
            if not api_key:
                logger.warning(
                    "No results for %r and GOOGLE_BOOKS_API_KEY is not set — "
                    "Google Books requires an API key for all requests. "
                    "Set GOOGLE_BOOKS_API_KEY in .env to enable the fallback.",
                    query,
                )
            else:
                logger.info("No OL/HC results — falling back to Google Books")
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

    # Tags
    categories: list[str] = vi.get("categories") or []
    tags = ", ".join(categories[:3]) if categories else None

    # Language: Google Books uses ISO 639-1 (e.g. "en")
    language = _normalize_language_code(vi.get("language"))

    return BookImportCandidate(
        title=vi["title"],
        subtitle=vi.get("subtitle") or None,
        author=author,
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
    author = None
    for c in contributions:
        author_name = c.get("author", {}).get("name")
        if author_name:
            author = author_name
            break

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


# ── Merge / Deduplicate ───────────────────────────────────────────────────────


def _merge_and_deduplicate(
    primary: list[BookImportCandidate],
    secondary: list[BookImportCandidate],
) -> list[BookImportCandidate]:
    """Merge two candidate lists, deduplicating by (isbn, page_count, language).

    Primary list items come first in the result.
    Same ISBN with different page_count/language is kept as separate candidates.
    When two candidates collide, the one with a cover image is preferred.
    """
    seen: dict[str, BookImportCandidate] = {}

    def _key(c: BookImportCandidate) -> str:
        isbn = (c.isbn or "").replace("-", "").replace(" ", "")
        pages = str(c.page_count or "")
        lang = (c.language or "").upper()
        return f"isbn:{isbn}|pages:{pages}|lang:{lang}"

    for c in primary + secondary:
        k = _key(c)
        existing = seen.get(k)
        if existing is None:
            seen[k] = c
        elif existing.cover_url is None and c.cover_url is not None:
            seen[k] = c

    return list(seen.values())


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
