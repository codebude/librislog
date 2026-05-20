from fastapi.testclient import TestClient


def test_cover_candidates_search_requires_valid_isbn(client: TestClient):
    resp = client.get("/api/cover-candidates/search?isbn=invalid")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid ISBN format"


def test_cover_candidates_search_returns_candidates(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

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
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

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
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

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
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

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


def test_rewrite_thalia_image_url():
    from app.routers.cover_candidates import _rewrite_thalia_image_url

    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/03/-/some/path.jpg"
    ) == "https://images.thalia.media/00/-/some/path.jpg"

    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/07/-/another/path.jpg"
    ) == "https://images.thalia.media/00/-/another/path.jpg"

    assert _rewrite_thalia_image_url(
        "https://example.com/03/-/cover.jpg"
    ) is None

    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/03"
    ) is None

    assert _rewrite_thalia_image_url("") is None


def _make_mock_page(suchtreffer: str | None = None, src: str | None = None, status: int = 200):
    """Helper to create a mock Scrapling page that returns desired css values."""
    class _MockResult:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def __bool__(self):
            return self._value is not None

        def __len__(self):
            return 1 if self._value is not None else 0

    class _MockPage:
        content = "<html></html>"

        def __init__(self):
            self.status = status

        def css(self, selector: str):
            if selector == 'dl-pageview::attr(suchtreffer)':
                return _MockResult(suchtreffer)
            if selector == 'suche-produktliste > div > ul > li:nth-child(1) > picture > img::attr(src)':
                return _MockResult(src)
            return _MockResult(None)

    return _MockPage()


def test_cover_candidates_thalia_disabled_by_setting(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)
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
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)
        async def post(self, url: str, **kwargs):
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["candidates"]) == 4

    sources = [item["source"] for item in data["candidates"]]
    assert "thalia" not in sources
    assert "hardcover" in sources
    assert "abebooks" in sources
    assert "openlibrary" in sources
    assert "amazon" in sources


def test_cover_candidates_thalia_enabled_and_found(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    mock_page = _make_mock_page(
        suchtreffer="1",
        src="https://images.thalia.media/03/-/some/path/cover.jpg",
    )

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs):
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            if "images.thalia.media" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["candidates"]) == 4

    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is True
    assert by_source["thalia"]["url"].startswith("https://images.thalia.media/00/-/")
    assert "03" not in by_source["thalia"]["url"]


def test_cover_candidates_thalia_zero_results(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    mock_page = _make_mock_page(suchtreffer="0", src=None)

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs):
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""


def test_cover_candidates_thalia_scrapling_error(client: TestClient, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs):
            raise Exception("Connection refused")

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str):
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def head(self, url: str, follow_redirects: bool = True):
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200

    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False


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
