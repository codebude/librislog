from fastapi.testclient import TestClient


def test_cover_candidates_search_requires_valid_isbn(client: TestClient):
    resp = client.get("/api/cover-candidates/search?isbn=invalid")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid ISBN format"


def test_cover_candidates_search_returns_candidates(client: TestClient, monkeypatch):
    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            if "abebooks" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "43210"}, url)
            if "openlibrary" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "900"}, url)
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router

    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
    assert resp.status_code == 200

    data = resp.json()
    assert data["query_isbn"] == "9780451524935"
    assert len(data["candidates"]) == 3

    by_source = {item["source"]: item for item in data["candidates"]}
    assert by_source["abebooks"]["available"] is True
    assert by_source["abebooks"]["filesize"] == 43210
    assert by_source["openlibrary"]["available"] is False
    assert by_source["amazon"]["available"] is False


def test_cover_candidates_search_accepts_isbn10(client: TestClient, monkeypatch):
    class _FakeResponse:
        def __init__(self, url: str):
            self.status_code = 200
            self.headers = {"content-type": "image/jpeg", "content-length": "5000"}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(url)

    import app.routers.cover_candidates as cover_candidates_router

    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=0451524934")
    assert resp.status_code == 200
    assert resp.json()["query_isbn"] == "9780451524935"
