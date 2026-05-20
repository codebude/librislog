import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_user
from app.config import settings
from app.models import User
from app.schemas import CoverCandidate, CoverCandidateList
from app.services.cover_import import is_safe_cover_import_url
from app.services.isbn_utils import isbn13_to_isbn10, normalize_isbn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cover-candidates", tags=["cover-candidates"])

_PROBE_SEMAPHORE = asyncio.Semaphore(20)

_THALIA_SEMAPHORE = asyncio.Semaphore(3)
_THALIA_FETCHER_CLASS = None


def _get_thalia_fetcher_class():
    global _THALIA_FETCHER_CLASS
    if _THALIA_FETCHER_CLASS is None:
        from scrapling import Fetcher

        _THALIA_FETCHER_CLASS = Fetcher
    return _THALIA_FETCHER_CLASS


def _extract_css_first(page, selector: str):
    values = page.css(selector)
    if not values:
        return None
    if hasattr(values, "get"):
        return values.get()
    return values[0]


def _rewrite_thalia_image_url(url: str) -> str | None:
    if not url.startswith("https://images.thalia.media/"):
        logger.debug("thalia URL does not match expected pattern: %s", url)
        return None

    prefix = "https://images.thalia.media/"
    rest = url[len(prefix):]

    slash_idx = rest.find("/")
    if slash_idx == -1:
        logger.debug("thalia URL has no path beyond first segment: %s", url)
        return None

    new_rest = "00" + rest[slash_idx:]
    return prefix + new_rest


def _fetch_thalia_page_sync(isbn13: str, timeout_seconds: int) -> str | None:
    search_url = f"https://www.thalia.de/suche?sq={isbn13}"

    try:
        fetcher_class = _get_thalia_fetcher_class()
        page = fetcher_class.get(
            search_url,
            timeout=timeout_seconds,
            impersonate="chrome",
        )
    except Exception as exc:
        logger.warning("thalia Fetcher failed for isbn=%s: %s", isbn13, exc)
        return None

    status = getattr(page, "status", None)
    if status == 403:
        logger.warning("thalia Fetcher blocked (403) for isbn=%s", isbn13)
        return None

    if page is None:
        return None

    try:
        suchtreffer = _extract_css_first(page, 'dl-pageview::attr(suchtreffer)')
    except Exception as exc:
        logger.debug("thalia failed to parse suchtreffer for isbn=%s: %s", isbn13, exc)
        return None

    if suchtreffer is None:
        logger.warning("thalia no suchtreffer attribute found for isbn=%s — possible site structure change", isbn13)
        return None

    try:
        result_count = int(suchtreffer)
    except (ValueError, TypeError) as exc:
        logger.debug("thalia invalid suchtreffer value for isbn=%s: %s", isbn13, exc)
        return None

    if result_count < 1:
        logger.debug("thalia zero search results for isbn=%s", isbn13)
        return None

    try:
        raw_url = _extract_css_first(
            page,
            'suche-produktliste > div > ul > li:nth-child(1) > picture > img::attr(src)'
        )
    except Exception as exc:
        logger.debug("thalia failed to parse image src for isbn=%s: %s", isbn13, exc)
        return None

    if raw_url is None:
        logger.warning("thalia no image src found for isbn=%s — possible site structure change", isbn13)
        return None

    raw_url = str(raw_url).strip()
    if not raw_url:
        logger.debug("thalia empty image src for isbn=%s", isbn13)
        return None

    rewritten_url = _rewrite_thalia_image_url(str(raw_url).strip())
    if not rewritten_url:
        logger.debug("thalia URL rewrite failed for isbn=%s raw_url=%s", isbn13, raw_url)
        return None

    logger.debug("thalia found url=%s (rewritten from %s) for isbn=%s", rewritten_url, raw_url, isbn13)
    return rewritten_url


async def _probe_thalia_candidate(
    isbn13: str,
    client: httpx.AsyncClient,
    min_size_bytes: int,
    timeout_seconds: int,
) -> CoverCandidate:
    async with _THALIA_SEMAPHORE:
        image_url = await asyncio.to_thread(_fetch_thalia_page_sync, isbn13, timeout_seconds)

    if not image_url:
        return CoverCandidate(
            source="thalia",
            url="",
            available=False,
        )

    if not is_safe_cover_import_url(image_url):
        logger.warning("thalia returned unsafe URL: %s", image_url)
        return CoverCandidate(
            source="thalia",
            url="",
            available=False,
        )

    return await _probe_candidate("thalia", image_url, client, min_size_bytes)


async def _query_hardcover_graphql(
    isbn13: str,
    client: httpx.AsyncClient,
    api_token: str,
) -> str | None:
    query = """
    query CoverQuery($isbn: String!) {
      book_mappings(limit: 1, where: {edition: {isbn_13: {_eq: $isbn}}}) {
        edition {
          image {
            url
          }
        }
      }
    }
    """

    variables = {"isbn": isbn13}

    try:
        async with _PROBE_SEMAPHORE:
            resp = await client.post(
                "https://api.hardcover.app/v1/graphql",
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {api_token}"},
            )

        if resp.status_code != 200:
            logger.debug(
                "hardcover GraphQL error status=%d body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return None

        data = resp.json()
        book_mappings = data.get("data", {}).get("book_mappings", [])
        if not book_mappings:
            logger.debug("hardcover no book_mappings for isbn=%s", isbn13)
            return None

        edition = book_mappings[0].get("edition", {})
        image = edition.get("image", {})
        url = image.get("url")

        if not url:
            logger.debug("hardcover no image URL for isbn=%s", isbn13)
            return None

        logger.debug("hardcover found url=%s for isbn=%s", url, isbn13)
        return url

    except Exception as exc:
        logger.warning("hardcover GraphQL query failed for isbn=%s: %s", isbn13, exc)
        return None


async def _probe_hardcover_candidate(
    client: httpx.AsyncClient,
    isbn13: str,
    api_token: str,
    min_size_bytes: int,
) -> CoverCandidate:
    image_url = await _query_hardcover_graphql(isbn13, client, api_token)

    if not image_url:
        return CoverCandidate(
            source="hardcover",
            url="",
            available=False,
        )

    if not is_safe_cover_import_url(image_url):
        logger.warning("hardcover returned unsafe URL: %s", image_url)
        return CoverCandidate(
            source="hardcover",
            url="",
            available=False,
        )

    return await _probe_candidate("hardcover", image_url, client, min_size_bytes)


async def _probe_candidate(
    source: str,
    url: str,
    client: httpx.AsyncClient,
    min_size_bytes: int,
) -> CoverCandidate:
    try:
        async with _PROBE_SEMAPHORE:
            resp = await client.head(url, follow_redirects=False)
        status_code = resp.status_code
        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip() or None
        content_length_header = resp.headers.get("content-length")
        filesize = None
        if content_length_header:
            try:
                filesize = int(content_length_header)
            except ValueError:
                filesize = None

        is_image = bool(content_type and content_type.startswith("image/"))
        large_enough = filesize is None or filesize >= min_size_bytes
        available = status_code == 200 and is_image and large_enough

        logger.debug(
            "cover probe source=%s url=%s status=%s content_type=%s filesize=%s is_image=%s large_enough=%s available=%s",
            source,
            url,
            status_code,
            content_type,
            filesize,
            is_image,
            large_enough,
            available,
        )

        if resp.status_code != 200:
            return CoverCandidate(source=source, url=url, available=False)

        return CoverCandidate(
            source=source,
            url=str(resp.url),
            available=available,
            filesize=filesize,
            content_type=content_type,
        )
    except Exception as exc:
        logger.debug("Cover candidate probe failed for %s (%s): %s", source, url, exc)
        return CoverCandidate(source=source, url=url, available=False)


async def _probe_source_candidates(
    source: str,
    urls: list[str],
    client: httpx.AsyncClient,
    min_size_bytes: int,
) -> CoverCandidate:
    first_candidate: CoverCandidate | None = None
    first_available: CoverCandidate | None = None
    logger.debug("cover source probe start source=%s urls=%s", source, urls)
    for url in urls:
        candidate = await _probe_candidate(source, url, client, min_size_bytes)
        if first_candidate is None:
            first_candidate = candidate
        if candidate.available and first_available is None:
            first_available = candidate
            logger.debug("cover source=%s selected candidate url=%s", source, candidate.url)
            break

    if first_available is not None:
        return first_available
    if first_candidate is not None:
        logger.debug("cover source=%s fallback candidate url=%s", source, first_candidate.url)
        return first_candidate
    return CoverCandidate(source=source, url=urls[0], available=False)


@router.get("/search", response_model=CoverCandidateList)
async def search_cover_candidates(
    isbn: str = Query(min_length=1),
    _current_user: User = Depends(require_user),
) -> CoverCandidateList:
    try:
        normalized_isbn13 = normalize_isbn(isbn)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISBN format")
    isbn10 = isbn13_to_isbn10(normalized_isbn13)
    logger.debug(
        "cover candidate search isbn_input=%s normalized_isbn13=%s isbn10=%s",
        isbn,
        normalized_isbn13,
        isbn10,
    )

    provider_urls: dict[str, list[str]] = {
        "abebooks": [f"https://pictures.abebooks.com/isbn/{normalized_isbn13}-de.jpg"],
        "openlibrary": [f"https://covers.openlibrary.org/b/isbn/{normalized_isbn13}-M.jpg"],
        "amazon": [f"https://images-eu.ssl-images-amazon.com/images/P/{normalized_isbn13}.01.L.jpg"],
    }
    if isbn10 is not None:
        provider_urls["abebooks"].append(f"https://pictures.abebooks.com/isbn/{isbn10}-de.jpg")
        provider_urls["openlibrary"].append(f"https://covers.openlibrary.org/b/isbn/{isbn10}-M.jpg")
        provider_urls["amazon"].append(f"https://images-eu.ssl-images-amazon.com/images/P/{isbn10}.01.L.jpg")

    logger.debug("cover candidate provider URLs: %s", provider_urls)

    timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
            for source, urls in provider_urls.items()
        ]

        if settings.hardcover_app_api_token.strip():
            logger.debug("cover candidate adding hardcover source (token configured)")
            tasks.append(
                _probe_hardcover_candidate(
                    client,
                    normalized_isbn13,
                    settings.hardcover_app_api_token,
                    settings.cover_candidate_min_size_bytes,
                )
            )
        else:
            logger.debug("cover candidate skipping hardcover (no token configured)")

        if settings.thalia_cover_search_enabled:
            logger.debug("cover candidate adding thalia source (enabled)")
            tasks.append(
                _probe_thalia_candidate(
                    normalized_isbn13,
                    client,
                    settings.cover_candidate_min_size_bytes,
                    settings.cover_candidate_timeout_seconds,
                )
            )
        else:
            logger.debug("cover candidate skipping thalia (disabled by config)")

        results = await asyncio.gather(*tasks)

    logger.debug("cover candidate results: %s", results)
    return CoverCandidateList(candidates=results, query_isbn=normalized_isbn13)
