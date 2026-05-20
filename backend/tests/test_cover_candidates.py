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


def test_cover_candidates_hardcover_with_token(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token_12345")

    requested_urls = []
    graphql_requests = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            if "assets.hardcover.app" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            graphql_requests.append((url, kwargs))
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {
                        "data": {
                            "book_mappings": [
                                {
                                    "edition": {
                                        "image": {
                                            "url": "https://assets.hardcover.app/editions/12345/cover.jpg"
                                        }
                                    }
                                }
                            ]
                        }
                    },
                )
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert data["query_isbn"] == "9783426440087"

    assert len(data["candidates"]) == 4

    by_source = {item["source"]: item for item in data["candidates"]}

    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is True
    assert "assets.hardcover.app" in by_source["hardcover"]["url"]

    assert by_source["abebooks"]["available"] is False
    assert by_source["openlibrary"]["available"] is False
    assert by_source["amazon"]["available"] is False

    assert len(graphql_requests) == 1
    gql_url, gql_kwargs = graphql_requests[0]
    assert "hardcover.app/v1/graphql" in gql_url
    assert "Authorization" in gql_kwargs["headers"]
    assert gql_kwargs["headers"]["Authorization"] == "Bearer test_token_12345"


def test_cover_candidates_hardcover_without_token(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    graphql_requests = []

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
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            graphql_requests.append((url, kwargs))
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()

    assert len(data["candidates"]) == 3

    sources = [item["source"] for item in data["candidates"]]
    assert "hardcover" not in sources
    assert "abebooks" in sources
    assert "openlibrary" in sources
    assert "amazon" in sources

    assert len(graphql_requests) == 0


def test_cover_candidates_hardcover_graphql_error(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, text=""):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            if "hardcover.app" in url:
                return _FakeResponse(401, {}, url, "Unauthorized")
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()

    assert len(data["candidates"]) == 4

    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False


def test_cover_candidates_hardcover_no_results(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {"data": {"book_mappings": []}},
                )
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()

    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""


def test_cover_candidates_hardcover_rejects_ssrf_url(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data=None):
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self):
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs):
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {
                        "data": {
                            "book_mappings": [
                                {
                                    "edition": {
                                        "image": {
                                            "url": "http://localhost:6379/"
                                        }
                                    }
                                }
                            ]
                        }
                    },
                )
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()

    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""
