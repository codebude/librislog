"""Anonymous, privacy-focused installation telemetry (best-effort).

Sends a minimal heartbeat — installation id, version, OS, CPU architecture
and runtime — to the LibrisLog telemetry API so that the project can track
how many installations exist, which versions are in use and on which
platforms they run.

This is an installation census, not user-behavior tracking. No user, book,
reading, host, network or configuration data is ever collected. The payload
is built strictly from the allow-list in :data:`TELEMETRY_FIELDS` and is
validated against it before sending.

Telemetry is best-effort and must never interfere with LibrisLog: network
failures are swallowed and only logged at debug level.
"""

import asyncio
import logging
import os
import platform
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app._build_info import __version__
from app.config import settings
from app.database import engine
from app.models import InstallationInfo

logger = logging.getLogger(__name__)

# Message version of the telemetry API schema (TelemetryInV1).
MESSAGE_VERSION = 1

# Fixed, generic user-agent so the transport carries no client-identifying
# details (httpx would otherwise send ``python-httpx/<version>``).
_USER_AGENT = "librislog-telemetry/1"

# Strict allow-list: the only fields a telemetry payload may ever contain.
TELEMETRY_FIELDS = frozenset(
    {
        "message_version",
        "installation_id",
        "version",
        "os",
        "architecture",
        "runtime",
        "client_ts",
    }
)

# Marker files indicating a containerized runtime. Kept generic on purpose:
# LibrisLog may run under Docker, containerd, Kubernetes, Podman, etc.
_CONTAINER_MARKERS = ("/.dockerenv", "/.containerenv")

# Runtime substrings looked up in /proc/1/cgroup to detect containerized
# environments that do not leave a marker file (e.g. containerd/Kubernetes).
_CONTAINER_CGROUP_MARKERS = ("docker", "containerd", "kubepods", "libpod", "lxc")


def normalize_os(system: str | None) -> str:
    """Normalize ``platform.system()`` output to lowercase."""
    return (system or "").strip().lower()


def normalize_architecture(machine: str | None) -> str:
    """Map common CPU architecture names to canonical values.

    ``x86_64``/``AMD64`` -> ``amd64``, ``aarch64``/``arm64`` -> ``arm64``.
    Anything else is reported as ``unknown``.
    """
    arch = (machine or "").strip().lower()
    if arch in {"x86_64", "amd64", "x64"}:
        return "amd64"
    if arch in {"aarch64", "arm64"}:
        return "arm64"
    return "unknown"


def _container_marker_present() -> bool:
    """Return True when a well-known container marker file exists."""
    return any(os.path.exists(marker) for marker in _CONTAINER_MARKERS)


def _cgroup_container_signal() -> bool | None:
    """Derive a container signal from ``/proc/1/cgroup`` without capturing it.

    Returns True when a container runtime path is present, False when the file
    is readable but contains no runtime marker, and None when it cannot be
    read. Only a boolean is derived — the file content (including any cgroup or
    container IDs) is never stored, logged, or sent.
    """
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return None
    return any(marker in content for marker in _CONTAINER_CGROUP_MARKERS)


def detect_runtime() -> str:
    """Detect whether LibrisLog runs inside a container or directly on a host.

    Returns ``container`` when a marker file is present or a container runtime
    appears in the cgroup paths, ``baremetal`` when the environment is readable
    and shows no container, and ``unknown`` when it cannot be determined.
    Container IDs and other environment-specific identifiers are never
    inspected, collected, or reported.
    """
    if _container_marker_present():
        return "container"
    signal = _cgroup_container_signal()
    if signal is True:
        return "container"
    if signal is False:
        return "baremetal"
    return "unknown"


def collect_system_info() -> dict[str, str]:
    """Collect the anonymous system attributes reported in the payload."""
    return {
        "os": normalize_os(platform.system()),
        "architecture": normalize_architecture(platform.machine()),
        "runtime": detect_runtime(),
    }


def get_or_create_installation_id(session: Session) -> str:
    """Return the persisted installation id, creating a random UUIDv4 once.

    The id is generated with ``uuid.uuid4()`` — a cryptographically random
    UUID completely independent of the host. It is stored in the database so
    it remains stable across restarts and updates. Deleting the database and
    reinstalling produces a fresh id.

    If two processes race on first boot and both try to insert the singleton
    row, the loser of the unique-primary-key race rolls back and re-reads the
    winner's row.
    """
    info = session.get(InstallationInfo, 1)
    if info is None:
        try:
            info = InstallationInfo(id=1, installation_id=str(uuid4()))
            session.add(info)
            session.commit()
            session.refresh(info)
        except IntegrityError:
            session.rollback()
            info = session.get(InstallationInfo, 1)
            if info is None:
                raise
    return info.installation_id


def build_payload(installation_id: str, client_ts: Optional[datetime] = None) -> dict[str, object]:
    """Build the telemetry payload using only allow-listed fields."""
    system = collect_system_info()
    payload = {
        "message_version": MESSAGE_VERSION,
        "installation_id": installation_id,
        "version": __version__,
        "os": system["os"],
        "architecture": system["architecture"],
        "runtime": system["runtime"],
        "client_ts": (client_ts or datetime.now(timezone.utc)).isoformat(),
    }
    if set(payload) != TELEMETRY_FIELDS:
        raise RuntimeError("telemetry payload contains fields outside the allow-list")
    return payload


def _load_installation_id() -> str:
    """Load (creating on first run) the installation id in its own session.

    The session is created, used and closed entirely inside the executor
    thread, so the event loop thread never touches a live SQLModel session.
    """
    with Session(engine) as session:
        return get_or_create_installation_id(session)


async def send_telemetry_once() -> None:
    """Send one best-effort telemetry heartbeat.

    Never raises: startup and the heartbeat loop must not be affected by
    telemetry problems. Failures are logged at debug level only.
    """
    if settings.telemetry_disabled:
        return
    loop = asyncio.get_running_loop()
    try:
        installation_id = await loop.run_in_executor(None, _load_installation_id)
        payload = build_payload(installation_id)
        async with httpx.AsyncClient(
            timeout=settings.telemetry_timeout_seconds, headers={"User-Agent": _USER_AGENT}
        ) as client:
            response = await client.post(settings.telemetry_endpoint, json=payload)
            response.raise_for_status()
        logger.debug("Telemetry heartbeat sent")
    except Exception as exc:  # noqa: BLE001 — telemetry must never interfere
        logger.debug("Telemetry heartbeat failed: %s", exc)