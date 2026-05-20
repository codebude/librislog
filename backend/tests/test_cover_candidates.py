from fastapi.testclient import TestClient


def test_cover_candidates_search_requires_valid_isbn(client: TestClient):
    resp = client.get("/api/cover-candidates/search?isbn=invalid")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid ISBN format"


def test_cover_candidates_search_returns_candidates(client: TestClient, monkeypatch):
    requested_urls = []

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
            requested_urls.append(url)
            if "abebooks" in url:
                response = _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "43210"}, url)
            elif "openlibrary" in url:
                response = _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "900"}, url)
            else:
                response = _FakeResponse(404, {}, url)

            return response

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
    assert any("9780451524935" in url for url in requested_urls)
    assert any("0451524934" in url for url in requested_urls)


def test_cover_candidates_search_accepts_isbn10(client: TestClient, monkeypatch):
    requested_urls = []

    class _FakeResponse:
        def __init__(self, status_code: int, url: str):
            self.status_code = status_code
            self.headers = {"content-type": "image/jpeg", "content-length": "5000"} if status_code == 200 else {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            if "0451524934" in url:
                response = _FakeResponse(200, url)
            else:
                response = _FakeResponse(404, url)

            return response

    import app.routers.cover_candidates as cover_candidates_router

    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=0451524934")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_isbn"] == "9780451524935"
    assert any("9780451524935" in url for url in requested_urls)
    assert any("0451524934" in url for url in requested_urls)


def test_cover_candidates_search_tries_isbn10_with_x_check_digit(client: TestClient, monkeypatch):
    requested_urls = []

    class _FakeResponse:
        def __init__(self, status_code: int, url: str):
            self.status_code = status_code
            self.headers = {"content-type": "image/jpeg", "content-length": "5000"} if status_code == 200 else {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            if "123456789X" in url:
                response = _FakeResponse(200, url)
            else:
                response = _FakeResponse(404, url)

            return response

    import app.routers.cover_candidates as cover_candidates_router

    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9781234567897")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_isbn"] == "9781234567897"
    assert any("9781234567897" in url for url in requested_urls)
    assert any("123456789X" in url for url in requested_urls)


def test_cover_candidates_search_979_isbn_does_not_probe_isbn10(client: TestClient, monkeypatch):
    requested_urls = []

    class _FakeResponse:
        def __init__(self, url: str):
            self.status_code = 404
            self.headers = {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            return _FakeResponse(url)

    import app.routers.cover_candidates as cover_candidates_router

    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9791234567896")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_isbn"] == "9791234567896"
    assert len(requested_urls) == 3
    assert all("9791234567896" in url for url in requested_urls)
