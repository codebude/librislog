import asyncio
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_user
from app.config import settings
from app.models import User
from app.schemas import CoverCandidate, CoverCandidateList

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cover-candidates", tags=["cover-candidates"])

_ISBN10_RE = re.compile(r"^\d{9}[\dX]$")
_ISBN13_RE = re.compile(r"^\d{13}$")
_PROBE_SEMAPHORE = asyncio.Semaphore(20)


def _normalize_isbn(isbn: str) -> str:
    compact = re.sub(r"[^0-9Xx]", "", isbn).upper()
    if _ISBN13_RE.fullmatch(compact):
        return compact

    if not _ISBN10_RE.fullmatch(compact):
        raise HTTPException(status_code=400, detail="Invalid ISBN format")

    core = compact[:-1]
    isbn13_core = f"978{core}"
    checksum_sum = sum(int(digit) * (1 if idx % 2 == 0 else 3) for idx, digit in enumerate(isbn13_core))
    checksum_digit = (10 - (checksum_sum % 10)) % 10
    return f"{isbn13_core}{checksum_digit}"


def _isbn13_to_isbn10(isbn13: str) -> str | None:
    if not _ISBN13_RE.fullmatch(isbn13):
        return None
    if not isbn13.startswith("978"):
        return None

    core9 = isbn13[3:-1]
    weighted_sum = sum(int(digit) * (10 - idx) for idx, digit in enumerate(core9))
    remainder = weighted_sum % 11
    check_value = 11 - remainder
    if check_value == 10:
        check_digit = "X"
    elif check_value == 11:
        check_digit = "0"
    else:
        check_digit = str(check_value)
    return f"{core9}{check_digit}"


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
    normalized_isbn13 = _normalize_isbn(isbn)
    isbn10 = _isbn13_to_isbn10(normalized_isbn13)
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
        results = await asyncio.gather(
            *[
                _probe_source_candidates(source, urls, client, settings.cover_candidate_min_size_bytes)
                for source, urls in provider_urls.items()
            ]
        )

    logger.debug("cover candidate results: %s", results)
    return CoverCandidateList(candidates=results, query_isbn=normalized_isbn13)
