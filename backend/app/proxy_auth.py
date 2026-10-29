"""Trusted reverse-proxy authentication helpers.

Kept separate from :mod:`app.main` so the public config endpoint can report the
effective (fail-closed) state without importing the application module.
"""

import ipaddress
import logging
import re
from collections.abc import Callable, Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import NamedTuple

from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
from app.database import create_session
from app.models import User

logger = logging.getLogger(__name__)

#: Header a proxy can set in addition to the identity header. Optional, but
#: recommended whenever the backend might be reachable directly.
SECRET_HEADER_NAME = "X-Trusted-Proxy-Secret"


class ProxyUser(NamedTuple):
    """The minimal user data proxy authentication needs."""

    id: int
    credentials_version: int


def _clean(value: str) -> str:
    """Strip inline comments and surrounding whitespace from an env value."""
    return value.split("#", 1)[0].strip()


def parse_ip_allow_list(value: str) -> set[str]:
    """Parse a comma/space-separated list of IP addresses and CIDR networks.

    ``*`` trusts any client. Invalid entries are skipped with a warning so a
    typo cannot silently widen or break the allow list.
    """
    raw = _clean(value)
    if not raw:
        return set()

    entries: set[str] = set()
    for item in raw.replace(",", " ").split():
        item = item.strip()
        if not item:
            continue
        if item == "*":
            entries.add("*")
            continue
        try:
            if "/" in item:
                entries.add(str(ipaddress.ip_network(item, strict=False)))
            else:
                address = ipaddress.ip_address(item)
                if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                    address = address.ipv4_mapped
                entries.add(str(address))
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy IP entry %r", item)
    return entries


@lru_cache(maxsize=16)
def _cached_ip_allow_list(value: str) -> frozenset[str]:
    """Parse the allow list once per distinct configuration value."""
    return frozenset(parse_ip_allow_list(value))


def trusted_ips() -> frozenset[str]:
    """Return the configured allow list, parsed once per distinct value."""
    return _cached_ip_allow_list(settings.trusted_proxy_auth_ips)


def ip_is_trusted(host: str | None, allow_list: set[str] | frozenset[str]) -> bool:
    """Return True when *host* matches the parsed allow list."""
    if not host:
        return False
    if "*" in allow_list:
        return True

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped

    for entry in allow_list:
        if entry == "*":
            return True
        try:
            if "/" in entry:
                if address in ipaddress.ip_network(entry):
                    return True
            elif address == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def header_name() -> str:
    """Return the configured identity header name."""
    return _clean(settings.trusted_proxy_auth_header)


def secret() -> str:
    """Return the optional shared secret.

    Do not strip inline ``#`` comments here: a secret may legitimately contain
    ``#``, and truncating it would silently lock the proxy out.
    """
    return settings.trusted_proxy_auth_secret.strip()


def _parse_user_map(value: str) -> dict[str, str]:
    """Parse ``proxy_user=email`` pairs separated by commas or whitespace.

    A comment starts at a ``#`` preceded by whitespace (or at the beginning of
    the value). A ``#`` inside a token is preserved, so usernames and local
    parts may contain it.
    """
    raw = value.strip()
    if not raw or raw.startswith("#"):
        return {}
    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    # Tolerate ``alice = alice@example.com`` before splitting on separators.
    raw = re.sub(r"\s*=\s*", "=", raw)

    mapping: dict[str, str] = {}
    for entry in re.split(r"[,\s]+", raw):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            logger.warning("Ignoring invalid trusted proxy user mapping entry %r", entry)
            continue
        proxy_user, email = entry.split("=", 1)
        proxy_user = proxy_user.strip().lower()
        email = email.strip()
        if not proxy_user or not email:
            logger.warning("Ignoring invalid trusted proxy user mapping entry %r", entry)
            continue
        if "=" in email:
            logger.warning(
                "Ignoring trusted proxy user mapping %r: value contains '='", entry
            )
            continue
        if "@" not in email:
            logger.warning(
                "Ignoring trusted proxy user mapping %r: value is not an email", entry
            )
            continue
        if proxy_user in mapping:
            logger.warning(
                "Trusted proxy user mapping overrides earlier entry for %r", proxy_user
            )
        mapping[proxy_user] = email
    return mapping


@lru_cache(maxsize=16)
def _cached_user_map(value: str) -> Mapping[str, str]:
    return MappingProxyType(_parse_user_map(value))


def user_map() -> Mapping[str, str]:
    """Return the optional proxy-user to email mapping.

    Keys are matched case-insensitively. Values are LibrisLog account emails.
    """
    return _cached_user_map(settings.trusted_proxy_auth_user_map)


def effective_identity(identity: str) -> str:
    """Return the account email a proxy identity maps to, before lookup."""
    raw = identity.strip()
    if not raw:
        return ""
    mapped = user_map().get(raw.lower())
    return (mapped or raw).strip().lower()


def is_active() -> bool:
    """Return True only when the feature is enabled and safely configured."""
    if not settings.trusted_proxy_auth_enabled:
        return False
    return bool(trusted_ips() and header_name())


_session_factory: Callable[[], Session] = create_session


def resolve_user(identity: str) -> ProxyUser | None:
    """Find exactly one existing user for a proxy identity.

    The identity is first looked up in the optional proxy-user mapping and then
    matched against user emails case-insensitively. Returns ``None`` when no
    user matches, when the address is ambiguous, or when the lookup fails. The
    caller must treat every non-match as anonymous access rather than as an
    error.
    """
    key = effective_identity(identity)
    if not key:
        return None

    with _session_factory() as session:
        rows = session.exec(
            select(User.id, User.credentials_version).where(func.lower(User.email) == key)
        ).all()

    if len(rows) > 1:
        logger.warning(
            "Trusted proxy email matched %d users; refusing to authenticate", len(rows)
        )
        return None
    if not rows:
        return None
    return ProxyUser(rows[0][0], rows[0][1])
