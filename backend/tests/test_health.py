"""Tests for app.routers.health module."""

from fastapi.testclient import TestClient


def test_health_quote_service_failure(client: TestClient, monkeypatch) -> None:
    """Quote service exception should report unhealthy."""
    monkeypatch.setattr("app.config.settings.dashboard_quote_enabled", True)

    class _ErrorClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_ErrorClient":
            return self

        async def __aexit__(self, *args: object, **kwargs: object) -> None:
            return None

        async def get(self, url: str) -> None:
            raise Exception("quote service down")

    monkeypatch.setattr("app.routers.health.httpx.AsyncClient", _ErrorClient)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["quote_service"]["status"] == "unhealthy"


def test_health_database_schema_exception(client: TestClient, monkeypatch) -> None:
    """Exception during schema inspection should report unhealthy."""
    def _raise(*args: object, **kwargs: object) -> None:
        raise Exception("inspector failed")

    monkeypatch.setattr("app.routers.health.inspect", _raise)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["database_schema"]["status"] == "unhealthy"


def test_health_database_schema_inspector_none(client: TestClient, monkeypatch) -> None:
    """When inspect(bind) returns None, schema check should report unhealthy."""
    def _inspect_none(bind):
        return None

    monkeypatch.setattr("app.routers.health.inspect", _inspect_none)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["database_schema"]["status"] == "unhealthy"
    assert "no inspector" in checks["database_schema"]["detail"].lower()


def test_health_not_sqlite(client: TestClient, monkeypatch) -> None:
    """Non-SQLite DB should skip data_dir_writable with skipped message."""
    monkeypatch.setattr(
        "app.config.settings.database_url", "postgresql://user:pass@localhost/db"
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["data_dir_writable"]["detail"] == "Skipped — not a SQLite database"


def test_health_in_memory_database(client: TestClient, monkeypatch) -> None:
    """In-memory SQLite should report skipped data_dir_writable check."""
    monkeypatch.setattr("app.config.settings.database_url", "sqlite:///:memory:")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["data_dir_writable"]["detail"] == "Skipped — in-memory database"


def test_health_sqlite_with_query_string(client: TestClient, monkeypatch) -> None:
    """SQLite URL with query string should strip it before path check."""
    monkeypatch.setattr(
        "app.config.settings.database_url", "sqlite:///./data/test.db?mode=rwc"
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["data_dir_writable"]["status"] == "healthy"


def test_health_data_dir_not_exist(client: TestClient, monkeypatch) -> None:
    """Non-existent data directory should report unhealthy."""
    monkeypatch.setattr(
        "app.config.settings.database_url", "sqlite:///./nonexistent_dir/test.db"
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert checks["data_dir_writable"]["status"] == "unhealthy"
