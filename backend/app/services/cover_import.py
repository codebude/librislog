import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.services.cover_storage import download_cover


def is_external_cover_url(url: str | None) -> bool:
    return bool(url and (url.startswith("http://") or url.startswith("https://")))


def is_safe_cover_import_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if not parsed.hostname:
        return False

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False

    if parsed.username or parsed.password:
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_restricted_ip(ip):
            return False
    except ValueError:
        try:
            resolved = socket.getaddrinfo(hostname, parsed.port or 80, type=socket.SOCK_STREAM)
        except OSError:
            return False

        for _, _, _, _, sockaddr in resolved:
            try:
                resolved_ip = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                return False
            if _is_restricted_ip(resolved_ip):
                return False

    return True


def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def import_cover_from_url(
    url: str,
    covers_dir: str | Path,
    user_id: int,
    timeout_seconds: int,
) -> str | None:
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
        return await download_cover(url, covers_dir, client, user_id)
