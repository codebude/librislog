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


async def _probe_candidate(
    source: str,
    url: str,
    client: httpx.AsyncClient,
    min_size_bytes: int,
) -> CoverCandidate:
    try:
        async with _PROBE_SEMAPHORE:
            resp = await client.head(url, follow_redirects=False)
        if resp.status_code != 200:
            return CoverCandidate(source=source, url=url, available=False)

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
        available = is_image and large_enough

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


@router.get("/search", response_model=CoverCandidateList)
async def search_cover_candidates(
    isbn: str = Query(min_length=1),
    _current_user: User = Depends(require_user),
) -> CoverCandidateList:
    normalized_isbn13 = _normalize_isbn(isbn)

    provider_urls = {
        "abebooks": f"https://pictures.abebooks.com/isbn/{normalized_isbn13}-de.jpg",
        "openlibrary": f"https://covers.openlibrary.org/b/isbn/{normalized_isbn13}-M.jpg",
        "amazon": f"https://images-eu.ssl-images-amazon.com/images/P/{normalized_isbn13}.01.L.jpg",
    }

    timeout = httpx.Timeout(settings.cover_candidate_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        results = await asyncio.gather(
            *[
                _probe_candidate(source, url, client, settings.cover_candidate_min_size_bytes)
                for source, url in provider_urls.items()
            ]
        )

    return CoverCandidateList(candidates=results, query_isbn=normalized_isbn13)
