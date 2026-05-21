"""Tests for custom Swagger / ReDoc documentation endpoints."""

from fastapi.testclient import TestClient


def test_custom_swagger_docs_available(client: TestClient) -> None:
    """Swagger UI should be served at /api/docs."""
    resp = client.get("/api/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Swagger UI" in resp.text
    assert "LibrisLog API - Swagger UI" in resp.text


def test_custom_redoc_docs_available(client: TestClient) -> None:
    """ReDoc should be served at /api/redoc."""
    resp = client.get("/api/redoc")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "ReDoc" in resp.text
    assert "LibrisLog API - ReDoc" in resp.text


def test_default_docs_redirect(client: TestClient) -> None:
    """Default /docs and /redoc should redirect to custom paths."""
    swagger_default = client.get("/docs", follow_redirects=False)
    redoc_default = client.get("/redoc", follow_redirects=False)
    assert swagger_default.status_code == 307
    assert swagger_default.headers["location"] == "/api/docs"
    assert redoc_default.status_code == 307
    assert redoc_default.headers["location"] == "/api/redoc"
