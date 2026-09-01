"""Tests for anonymous installation telemetry."""

import asyncio
import platform
import socket
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models import InstallationInfo


# --- OS / architecture / runtime normalization ---------------------------------


def test_os_normalized_to_lowercase() -> None:
    """OS names should be normalized to lowercase."""
    from app.services.telemetry import normalize_os

    assert normalize_os("Linux") == "linux"
    assert normalize_os("Darwin") == "darwin"
    assert normalize_os("Windows") == "windows"
    assert normalize_os("") == ""
    assert normalize_os(None) == ""


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        ("x86_64", "amd64"),
        ("AMD64", "amd64"),
        ("x64", "amd64"),
        ("aarch64", "arm64"),
        ("arm64", "arm64"),
        ("armv7l", "unknown"),
        ("i386", "unknown"),
        ("ppc64le", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_architecture_normalization(machine: str | None, expected: str) -> None:
    """Common architectures are normalized, unknown ones become ``unknown``."""
    from app.services.telemetry import normalize_architecture

    assert normalize_architecture(machine) == expected


def test_linux_is_detected() -> None:
    """On Linux, the OS should be reported as ``linux``."""
    from app.services.telemetry import collect_system_info, normalize_os

    assert normalize_os(platform.system()) == platform.system().lower()
    info = collect_system_info()
    assert set(info) == {"os", "architecture", "runtime"}
    assert "os" in info


def test_collect_system_info_reports_only_three_fields(monkeypatch) -> None:
    """System info must contain exactly the three telemetry fields."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "normalize_os", lambda s: "linux")
    monkeypatch.setattr(telemetry, "normalize_architecture", lambda m: "amd64")
    monkeypatch.setattr(telemetry, "detect_runtime", lambda: "container")

    info = telemetry.collect_system_info()
    assert info == {"os": "linux", "architecture": "amd64", "runtime": "container"}


def test_detect_runtime_container_marker(monkeypatch) -> None:
    """A ``/.dockerenv`` marker should report ``container``."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "_container_marker_present", lambda: True)
    monkeypatch.setattr(telemetry, "_cgroup_container_signal", lambda: False)
    assert telemetry.detect_runtime() == "container"


def test_detect_runtime_container_via_cgroup(monkeypatch) -> None:
    """A container runtime in the cgroup paths should report ``container``."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "_container_marker_present", lambda: False)
    monkeypatch.setattr(telemetry, "_cgroup_container_signal", lambda: True)
    assert telemetry.detect_runtime() == "container"


def test_detect_runtime_baremetal(monkeypatch) -> None:
    """A readable cgroup without a container runtime should report ``baremetal``."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "_container_marker_present", lambda: False)
    monkeypatch.setattr(telemetry, "_cgroup_container_signal", lambda: False)
    assert telemetry.detect_runtime() == "baremetal"


def test_detect_runtime_unknown_when_unreadable(monkeypatch) -> None:
    """When no marker exists and the cgroup cannot be read, report ``unknown``."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "_container_marker_present", lambda: False)
    monkeypatch.setattr(telemetry, "_cgroup_container_signal", lambda: None)
    assert telemetry.detect_runtime() == "unknown"


def test_detect_runtime_only_checks_known_marker_files(monkeypatch) -> None:
    """Only the well-known marker files are probed — never arbitrary paths."""
    from app.services import telemetry

    monkeypatch.setattr(telemetry, "_CONTAINER_MARKERS", ("/.dockerenv", "/.containerenv"))
    monkeypatch.setattr(telemetry, "_cgroup_container_signal", lambda: None)
    with patch("os.path.exists", return_value=False) as mock_exists:
        assert telemetry.detect_runtime() == "unknown"
    checked = {call.args[0] for call in mock_exists.call_args_list}
    assert checked == {"/.dockerenv", "/.containerenv"}


def test_cgroup_detection_never_exposes_ids(monkeypatch) -> None:
    """The cgroup probe returns a boolean — never the raw content or container IDs."""
    from app.services import telemetry

    class FakeFile:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> str:
            return "0::/docker/0123456789abcdef\n"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: FakeFile())
    assert telemetry._cgroup_container_signal() is True

    class CleanFile(FakeFile):
        def read(self) -> str:
            return "0::/init.scope\n"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: CleanFile())
    assert telemetry._cgroup_container_signal() is False


def test_cgroup_detection_handles_unreadable(monkeypatch) -> None:
    """An unreadable cgroup file yields None (undetermined)."""
    from app.services import telemetry

    def _raise(*args, **kwargs):
        raise OSError("no /proc/1/cgroup")

    monkeypatch.setattr("builtins.open", _raise)
    assert telemetry._cgroup_container_signal() is None


# --- Installation id ------------------------------------------------------------


def test_new_installation_receives_random_uuid4(session: Session) -> None:
    """A fresh installation should get a random UUIDv4."""
    from app.services.telemetry import get_or_create_installation_id

    installation_id = get_or_create_installation_id(session)
    assert uuid.UUID(installation_id).version == 4
    persisted = session.get(InstallationInfo, 1)
    assert persisted is not None
    assert persisted.installation_id == installation_id


def _installation_id_from_fresh_db() -> str:
    """Create a fresh DB and return the installation id generated in it."""
    from app.services.telemetry import get_or_create_installation_id

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            return get_or_create_installation_id(session)
    finally:
        engine.dispose()


def test_installation_id_differs_between_fresh_installs() -> None:
    """Two independent installations must get different ids."""
    assert _installation_id_from_fresh_db() != _installation_id_from_fresh_db()


def test_installation_id_stable_across_starts() -> None:
    """The id must stay stable across subsequent application starts."""
    from app.services.telemetry import get_or_create_installation_id

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            first = get_or_create_installation_id(session)
        with Session(engine) as session:
            second = get_or_create_installation_id(session)
    finally:
        engine.dispose()

    assert first == second
    assert uuid.UUID(first).version == 4


def test_installation_id_not_derived_from_mac_or_hostname(session: Session) -> None:
    """The id must be a random UUIDv4, not a deterministic host-derived value."""
    from app.services.telemetry import get_or_create_installation_id

    installation_id = get_or_create_installation_id(session)
    parsed = uuid.UUID(installation_id)
    assert parsed.version == 4

    assert installation_id != str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
    assert installation_id != str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode())))
    # The UUID's random bits must not be the machine node id.
    assert parsed.node != uuid.getnode()


def test_installation_id_recovers_from_insert_race(session: Session) -> None:
    """If the singleton insert loses a concurrent-worker race, re-read the winner's row."""
    from app.services.telemetry import get_or_create_installation_id

    existing_id = "existing-0000-0000-4000-8000-000000000001"
    session.add(InstallationInfo(id=1, installation_id=existing_id))
    session.commit()

    real_get = session.get
    calls = {"count": 0}

    def fake_get(model, pk):
        calls["count"] += 1
        if calls["count"] == 1:
            return None  # simulate a concurrent worker not yet seeing the row
        return real_get(model, pk)

    with patch.object(session, "get", side_effect=fake_get):
        got = get_or_create_installation_id(session)

    assert got == existing_id
    assert calls["count"] == 2


# --- Payload ---------------------------------------------------------------------


def test_payload_contains_only_allowed_fields() -> None:
    """The payload may only contain the strictly allow-listed fields."""
    from app._build_info import __version__
    from app.services.telemetry import TELEMETRY_FIELDS, build_payload

    installation_id = "11111111-2222-4333-8444-555555555555"
    payload = build_payload(installation_id)

    assert set(payload) == TELEMETRY_FIELDS
    assert payload["message_version"] == 1
    assert payload["installation_id"] == installation_id
    assert payload["version"] == __version__
    assert payload["os"] == platform.system().lower()
    assert payload["architecture"] in {"amd64", "arm64", "unknown"}
    assert payload["runtime"] in {"container", "baremetal", "unknown"}
    assert payload["client_ts"]  # non-empty ISO timestamp


def test_build_payload_rejects_unknown_fields() -> None:
    """Adding a field outside the allow-list must raise."""
    from app.services import telemetry
    from app.services.telemetry import build_payload

    with patch.object(telemetry, "collect_system_info", return_value={"os": "linux", "architecture": "amd64", "runtime": "unknown"}):
        with patch.object(telemetry, "TELEMETRY_FIELDS", frozenset({"message_version", "installation_id"})):
            with pytest.raises(RuntimeError, match="allow-list"):
                build_payload("some-id")


# --- Sending ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_telemetry_disabled_prevents_any_request(session: Session, monkeypatch) -> None:
    """With telemetry disabled, no HTTP request may be made."""
    from app.config import settings
    from app.services import telemetry

    monkeypatch.setattr(settings, "telemetry_disabled", True)

    with patch("httpx.AsyncClient") as mock_client:
        await telemetry.send_telemetry_once()

    mock_client.assert_not_called()


@pytest.mark.anyio
async def test_send_telemetry_posts_allowlisted_payload(session: Session, monkeypatch) -> None:
    """An enabled send should POST exactly the allow-listed payload once."""
    from app.config import settings
    from app.services import telemetry

    monkeypatch.setattr(settings, "telemetry_disabled", False)
    monkeypatch.setattr(settings, "telemetry_endpoint", "https://telemetry.test/api/telemetry")
    monkeypatch.setattr(
        telemetry, "_load_installation_id", lambda: telemetry.get_or_create_installation_id(session)
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls = MagicMock(return_value=mock_client)

    with patch("httpx.AsyncClient", mock_client_cls):
        await telemetry.send_telemetry_once()

    mock_client_cls.assert_called_once_with(
        timeout=settings.telemetry_timeout_seconds,
        headers={"User-Agent": telemetry._USER_AGENT},
    )
    mock_client.post.assert_awaited_once()
    call = mock_client.post.await_args
    assert call is not None
    assert call.args[0] == settings.telemetry_endpoint
    sent = call.kwargs["json"]
    assert set(sent) == telemetry.TELEMETRY_FIELDS
    assert sent["message_version"] == 1
    assert uuid.UUID(sent["installation_id"]).version == 4

    persisted = session.get(InstallationInfo, 1)
    assert persisted is not None
    assert persisted.installation_id == sent["installation_id"]


@pytest.mark.anyio
async def test_send_telemetry_end_to_end_with_real_session(tmp_path, monkeypatch) -> None:
    """A send using the real session/engine path persists the id and posts."""
    from sqlmodel import SQLModel, Session, create_engine

    from app.config import settings
    from app.services import telemetry

    engine = create_engine(
        f"sqlite:///{tmp_path / 'telemetry.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(telemetry, "engine", engine)
    monkeypatch.setattr(settings, "telemetry_disabled", False)
    monkeypatch.setattr(settings, "telemetry_endpoint", "https://telemetry.test/api/telemetry")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls = MagicMock(return_value=mock_client)

    try:
        with patch("httpx.AsyncClient", mock_client_cls):
            await telemetry.send_telemetry_once()

        mock_client.post.assert_awaited_once()
        with Session(engine) as session:
            persisted = session.get(InstallationInfo, 1)
    finally:
        engine.dispose()
    assert persisted is not None
    assert uuid.UUID(persisted.installation_id).version == 4


@pytest.mark.anyio
async def test_network_failure_is_swallowed(session: Session, monkeypatch) -> None:
    """A network failure must not raise out of send_telemetry_once."""
    from app.config import settings
    from app.services import telemetry

    monkeypatch.setattr(settings, "telemetry_disabled", False)
    monkeypatch.setattr(
        telemetry, "_load_installation_id", lambda: telemetry.get_or_create_installation_id(session)
    )

    with patch("httpx.AsyncClient", side_effect=httpx.ConnectError("boom")):
        await telemetry.send_telemetry_once()  # must not raise


@pytest.mark.anyio
async def test_database_failure_is_swallowed(monkeypatch) -> None:
    """A database failure must not raise and must not send a request."""
    from app.config import settings
    from app.services import telemetry

    monkeypatch.setattr(settings, "telemetry_disabled", False)
    monkeypatch.setattr(
        telemetry, "_load_installation_id", MagicMock(side_effect=RuntimeError("db down"))
    )

    with patch("httpx.AsyncClient") as mock_client:
        await telemetry.send_telemetry_once()  # must not raise

    mock_client.assert_not_called()


@pytest.mark.anyio
async def test_heartbeat_sends_then_waits_24h() -> None:
    """The heartbeat sends on start, then sleeps 24h and keeps going on failure."""
    import app.main as main_module

    calls = 0

    async def failing_send() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    mock_sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    with patch("app.main.send_telemetry_once", new=failing_send):
        with patch("app.main.asyncio.sleep", new=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await main_module._telemetry_heartbeat()

    assert calls == 2
    assert mock_sleep.call_args_list[0].args[0] == 24 * 3600


@pytest.mark.anyio
async def test_startup_continues_when_telemetry_fails(monkeypatch) -> None:
    """Lifespan must complete normally even if the telemetry heartbeat errors."""
    from app.config import settings
    import app.main as main_module

    monkeypatch.setattr(settings, "telemetry_disabled", False)
    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with patch("app.main.send_telemetry_once", new=AsyncMock(side_effect=RuntimeError("boom"))):
            async with main_module.lifespan(main_module.app):
                pass


@pytest.mark.anyio
async def test_lifespan_starts_telemetry_task_when_enabled(monkeypatch) -> None:
    """When telemetry is enabled, a heartbeat task is started at startup."""
    from app.config import settings
    import app.main as main_module

    monkeypatch.setattr(settings, "telemetry_disabled", False)
    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with patch("app.main._telemetry_heartbeat", new=AsyncMock()) as mock_heartbeat:
            async with main_module.lifespan(main_module.app):
                await asyncio.sleep(0)

    mock_heartbeat.assert_awaited_once()


@pytest.mark.anyio
async def test_lifespan_skips_telemetry_when_disabled(monkeypatch) -> None:
    """When telemetry is disabled, no heartbeat task may be started."""
    from app.config import settings
    import app.main as main_module

    monkeypatch.setattr(settings, "telemetry_disabled", True)
    with patch("app.main._periodic_maintenance", new=AsyncMock()):
        with patch("app.main._telemetry_heartbeat", new=AsyncMock()) as mock_heartbeat:
            async with main_module.lifespan(main_module.app):
                pass

    mock_heartbeat.assert_not_called()