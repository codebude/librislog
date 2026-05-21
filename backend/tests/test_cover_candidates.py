from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def test_cover_candidates_search_requires_valid_isbn(client: TestClient) -> None:
    resp = client.get("/api/cover-candidates/search?isbn=invalid")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid ISBN format"


def test_cover_candidates_search_returns_candidates(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    requested_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
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


def test_cover_candidates_search_accepts_isbn10(client: TestClient, monkeypatch) -> None:
    requested_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, status_code: int, url: str) -> None:
            self.status_code = status_code
            self.headers = {"content-type": "image/jpeg", "content-length": "5000"} if status_code == 200 else {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
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


def test_cover_candidates_search_tries_isbn10_with_x_check_digit(client: TestClient, monkeypatch) -> None:
    requested_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, status_code: int, url: str) -> None:
            self.status_code = status_code
            self.headers = {"content-type": "image/jpeg", "content-length": "5000"} if status_code == 200 else {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
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


def test_cover_candidates_search_979_isbn_does_not_probe_isbn10(client: TestClient, monkeypatch) -> None:
    requested_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, url: str) -> None:
            self.status_code = 404
            self.headers: dict[str, str] = {}
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
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


def test_cover_candidates_hardcover_with_token(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token_12345")
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    requested_urls: list[str] = []
    graphql_requests: list[tuple[str, dict]] = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self) -> dict:
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            requested_urls.append(url)
            if "assets.hardcover.app" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            graphql_requests.append((url, kwargs))
            if "hardcover.app" in url:
                return _FakeResponse(
                    200,
                    {"content-type": "application/json"},
                    url,
                    {
                        "data": {
                            "book_mappings": [
                                {"edition": {"image": {"url": "https://assets.hardcover.app/editions/12345/cover.jpg"}}}
                            ]
                        }
                    },
                )
            return _FakeResponse(404, {}, url)  # pragma: no cover

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
    assert len(graphql_requests) == 1
    gql_url, gql_kwargs = graphql_requests[0]
    assert "hardcover.app/v1/graphql" in gql_url
    assert gql_kwargs["headers"]["Authorization"] == "Bearer test_token_12345"


def test_cover_candidates_hardcover_without_token(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    graphql_requests: list[tuple[str, dict]] = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            graphql_requests.append((url, kwargs))  # pragma: no cover
            return _FakeResponse(404, {}, url)  # pragma: no cover

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 3
    sources = [item["source"] for item in data["candidates"]]
    assert "hardcover" not in sources
    assert len(graphql_requests) == 0


def test_cover_candidates_hardcover_graphql_error(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, text: str = "") -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self.text = text

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            if "hardcover.app" in url:
                return _FakeResponse(401, {}, url, "Unauthorized")
            return _FakeResponse(404, {}, url)  # pragma: no cover

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 4
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False


def test_cover_candidates_hardcover_no_results(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self) -> dict:
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            if "hardcover.app" in url:
                return _FakeResponse(200, {"content-type": "application/json"}, url, {"data": {"book_mappings": []}})
            return _FakeResponse(404, {}, url)  # pragma: no cover

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""


def test_rewrite_thalia_image_url() -> None:
    from app.routers.cover_candidates import _rewrite_thalia_image_url

    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/03/-/some/path.jpg"
    ) == "https://images.thalia.media/00/-/some/path.jpg"
    assert _rewrite_thalia_image_url(
        "https://images.thalia.media/07/-/another/path.jpg"
    ) == "https://images.thalia.media/00/-/another/path.jpg"
    assert _rewrite_thalia_image_url("https://example.com/03/-/cover.jpg") is None
    assert _rewrite_thalia_image_url("https://images.thalia.media/03") is None
    assert _rewrite_thalia_image_url("") is None


def _make_mock_page(
    suchtreffer: str | None = None,
    src: str | None = None,
    status: int = 200,
):
    """Helper to create a mock Scrapling page that returns element objects with attributes."""
    class _MockElement:
        def __init__(self, attrs: dict[str, str] | None = None) -> None:
            self.attrib = attrs or {}
            self.text = ""

    class _MockElements:
        def __init__(self, items: list) -> None:
            self._items = items

        def __getitem__(self, index: int) -> _MockElement:
            return self._items[index]

        def __bool__(self) -> bool:
            return len(self._items) > 0

        def __len__(self) -> int:  # pragma: no cover
            return len(self._items)

    class _MockPage:
        content = "<html></html>"

        def __init__(self) -> None:
            self.status = status

        def css(self, selector: str, auto_save: bool = False, adaptive: bool = False) -> _MockElements:
            if selector == "dl-pageview":
                if suchtreffer is not None:
                    return _MockElements([_MockElement({"suchtreffer": suchtreffer})])
                return _MockElements([])
            if selector == "suche-produktliste > div > ul > li:nth-child(1) > picture > img":
                if src is not None:
                    return _MockElements([_MockElement({"src": src})])
                return _MockElements([])  # pragma: no cover
            return _MockElements([])  # pragma: no cover

    return _MockPage()


def test_cover_candidates_thalia_disabled_by_setting(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}
        def json(self) -> dict:
            return self._json_data  # pragma: no cover

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)
        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 4
    sources = [item["source"] for item in data["candidates"]]
    assert "thalia" not in sources


def test_cover_candidates_thalia_enabled_and_found(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module
    mock_page = _make_mock_page(suchtreffer="1", src="https://images.thalia.media/03/-/some/path/cover.jpg")

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
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


def test_cover_candidates_thalia_zero_results(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module
    mock_page = _make_mock_page(suchtreffer="0", src=None)

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""


def test_cover_candidates_thalia_scrapling_error(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            raise Exception("Connection refused")

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False


def test_cover_candidates_hardcover_rejects_ssrf_url(client: TestClient, monkeypatch) -> None:
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}
        def json(self) -> dict:
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)
        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            if "hardcover.app" in url:
                return _FakeResponse(
                    200, {"content-type": "application/json"}, url,
                    {"data": {"book_mappings": [{"edition": {"image": {"url": "http://localhost:6379/"}}}]}},
                )
            return _FakeResponse(404, {}, url)  # pragma: no cover

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""


def _make_adaptive_mock_page(first_empty: bool = False):
    """Mock page where Phase 1 (auto_save) returns empty, Phase 2 (adaptive) finds elements."""
    class _MockElement:
        def __init__(self, attrs: dict[str, str] | None = None) -> None:
            self.attrib = attrs or {}
            self.text = ""

    class _MockElements:
        def __init__(self, items: list) -> None:
            self._items = items
        def __getitem__(self, index: int) -> _MockElement:
            return self._items[index]
        def __bool__(self) -> bool:
            return len(self._items) > 0
        def __len__(self) -> int:  # pragma: no cover
            return len(self._items)

    class _AdaptiveMockPage:
        content = "<html></html>"
        status = 200

        def __init__(self) -> None:
            self._first_call = True

        def css(self, selector: str, auto_save: bool = False, adaptive: bool = False) -> _MockElements:
            if adaptive and first_empty:
                if "dl-pageview" in selector:
                    return _MockElements([_MockElement({"suchtreffer": "1"})])
                return _MockElements([_MockElement({"src": "https://images.thalia.media/03/-/adaptive/cover.jpg"})])
            if auto_save and first_empty and not adaptive:
                return _MockElements([])  # pragma: no cover
            if "dl-pageview" in selector:  # pragma: no cover
                return _MockElements([_MockElement({"suchtreffer": "1"})])  # pragma: no cover
            return _MockElements([_MockElement({"src": "https://images.thalia.media/03/-/normal/cover.jpg"})])  # pragma: no cover

    return _AdaptiveMockPage()


def test_cover_candidates_thalia_adaptive_fallback(client: TestClient, monkeypatch) -> None:
    """When exact selector fails, adaptive fallback re-finds elements."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module
    adaptive_page = _make_adaptive_mock_page(first_empty=True)

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return adaptive_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            if "images.thalia.media" in url:
                return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "50000"}, url)
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is True
    assert by_source["thalia"]["url"].startswith("https://images.thalia.media/00/-/")


def test_cover_candidates_thalia_403_blocked(client: TestClient, monkeypatch) -> None:
    """Thalia returns unavailable when Fetcher gets a 403 response."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return _make_mock_page(status=403)

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""


def test_cover_candidates_thalia_suchtreffer_not_found(client: TestClient, monkeypatch) -> None:
    """Thalia returns unavailable when dl-pageview element has no suchtreffer attr."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module
    mock_page = _make_mock_page(suchtreffer=None, src=None)

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> object:
            from types import SimpleNamespace
            return SimpleNamespace(status_code=404, headers={}, url=url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""


def test_cover_candidates_thalia_empty_image_src(client: TestClient, monkeypatch) -> None:
    """Thalia returns unavailable when img src attribute is empty string."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", True)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    import app.routers.cover_candidates as cc_module
    mock_page = _make_mock_page(suchtreffer="1", src="")

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr(cc_module, "_THALIA_FETCHER_CLASS", _FakeFetcher)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)

    monkeypatch.setattr(cc_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "thalia" in by_source
    assert by_source["thalia"]["available"] is False
    assert by_source["thalia"]["url"] == ""


def test_cover_candidates_probe_content_length_value_error(client: TestClient, monkeypatch) -> None:
    """Cover probe handles invalid Content-Length header gracefully."""
    from app import config
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "")

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(200, {"content-type": "image/jpeg", "content-length": "not-a-number"}, url)

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert by_source["abebooks"]["available"] is True
    assert by_source["abebooks"]["filesize"] is None


def test_cover_candidates_probe_exception(client: TestClient, monkeypatch) -> None:
    """Cover probe returns unavailable on network exception."""
    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> None:
            raise ConnectionError("network failure")

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9780451524935")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert by_source["abebooks"]["available"] is False


def test_cover_candidates_hardcover_no_image_url(client: TestClient, monkeypatch) -> None:
    """Hardcover returns unavailable when book_mappings has no image.url."""
    from app import config
    monkeypatch.setattr(config.settings, "hardcover_app_api_token", "test_token")
    monkeypatch.setattr(config.settings, "thalia_cover_search_enabled", False)

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], url: str, json_data: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = url
            self._json_data = json_data or {}

        def json(self) -> dict:
            return self._json_data

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass
        async def __aenter__(self) -> "_FakeAsyncClient":
            return self
        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False
        async def head(self, url: str, follow_redirects: bool = True) -> _FakeResponse:
            return _FakeResponse(404, {}, url)
        async def post(self, url: str, **kwargs: object) -> _FakeResponse:
            return _FakeResponse(
                200, {"content-type": "application/json"}, url,
                {"data": {"book_mappings": [{"edition": {"image": {}}}]}},
            )

    import app.routers.cover_candidates as cover_candidates_router
    monkeypatch.setattr(cover_candidates_router.httpx, "AsyncClient", _FakeAsyncClient)

    resp = client.get("/api/cover-candidates/search?isbn=9783426440087")
    assert resp.status_code == 200
    data = resp.json()
    by_source = {item["source"]: item for item in data["candidates"]}
    assert "hardcover" in by_source
    assert by_source["hardcover"]["available"] is False
    assert by_source["hardcover"]["url"] == ""


# ── _extract_css_adaptive direct tests ────────────────────────────────────────


def test_extract_css_adaptive_text_without_attr_phase1() -> None:
    from app.routers.cover_candidates import _extract_css_adaptive

    class _Elem:
        text = "Hello"
        attrib: dict[str, str] = {}

    class _Elements:
        def __init__(self, items: list) -> None:
            self._items = items
        def __getitem__(self, index: int) -> _Elem:
            return self._items[index]
        def __bool__(self) -> bool:
            return len(self._items) > 0

    class _Page:
        def css(self, selector: str, auto_save: bool = False, adaptive: bool = False) -> _Elements:
            return _Elements([_Elem()])

    page = _Page()
    assert _extract_css_adaptive(page, "div") == "Hello"


def test_extract_css_adaptive_text_without_attr_phase2() -> None:
    from app.routers.cover_candidates import _extract_css_adaptive

    class _Elem:
        text = "Adaptive"
        attrib: dict[str, str] = {}

    class _Elements:
        def __init__(self, items: list) -> None:
            self._items = items
        def __getitem__(self, index: int) -> _Elem:
            return self._items[index]
        def __bool__(self) -> bool:
            return len(self._items) > 0

    class _Page:
        def css(self, selector: str, auto_save: bool = False, adaptive: bool = False) -> _Elements:
            if adaptive:
                return _Elements([_Elem()])
            return _Elements([])

    page = _Page()
    assert _extract_css_adaptive(page, "div") == "Adaptive"


# ── _fetch_thalia_page_sync direct tests ──────────────────────────────────────


def test_fetch_thalia_page_sync_returns_none_when_page_is_none(monkeypatch) -> None:
    from app.routers.cover_candidates import _fetch_thalia_page_sync

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> None:
            return None

    monkeypatch.setattr("app.routers.cover_candidates._THALIA_FETCHER_CLASS", _FakeFetcher)
    result = _fetch_thalia_page_sync("9783426440087", 10)
    assert result is None


def test_fetch_thalia_page_sync_returns_none_on_suchtreffer_exception(monkeypatch) -> None:
    from app.routers.cover_candidates import _fetch_thalia_page_sync

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return _make_mock_page()

    monkeypatch.setattr("app.routers.cover_candidates._THALIA_FETCHER_CLASS", _FakeFetcher)

    def fake_extract(page: object, selector: str, attr: str | None = None) -> str | None:
        if selector == "dl-pageview":
            raise ValueError("parse error")
        return None  # pragma: no cover

    monkeypatch.setattr("app.routers.cover_candidates._extract_css_adaptive", fake_extract)
    result = _fetch_thalia_page_sync("9783426440087", 10)
    assert result is None


def test_fetch_thalia_page_sync_returns_none_on_image_src_exception(monkeypatch) -> None:
    from app.routers.cover_candidates import _fetch_thalia_page_sync

    mock_page = _make_mock_page(suchtreffer="1", src=None)

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr("app.routers.cover_candidates._THALIA_FETCHER_CLASS", _FakeFetcher)

    def fake_extract(page: object, selector: str, attr: str | None = None) -> str | None:
        if selector == "suche-produktliste > div > ul > li:nth-child(1) > picture > img":
            raise ValueError("parse error")
        if selector == "dl-pageview":
            return "1"
        return None  # pragma: no cover

    monkeypatch.setattr("app.routers.cover_candidates._extract_css_adaptive", fake_extract)
    result = _fetch_thalia_page_sync("9783426440087", 10)
    assert result is None


def test_fetch_thalia_page_sync_returns_none_on_empty_image_src(monkeypatch) -> None:
    from app.routers.cover_candidates import _fetch_thalia_page_sync

    mock_page = _make_mock_page(suchtreffer="1", src="   ")

    class _FakeFetcher:
        @classmethod
        def get(cls, url: str, **kwargs: object) -> object:
            return mock_page

    monkeypatch.setattr("app.routers.cover_candidates._THALIA_FETCHER_CLASS", _FakeFetcher)
    result = _fetch_thalia_page_sync("9783426440087", 10)
    assert result is None


# ── _probe_thalia_candidate direct tests ──────────────────────────────────────


def test_probe_thalia_rejects_unsafe_url(monkeypatch) -> None:
    import asyncio
    from app.routers.cover_candidates import _probe_thalia_candidate

    def fake_fetch(*args: object, **kwargs: object) -> str:
        return "http://unsafe.com/cover.jpg"

    monkeypatch.setattr("app.routers.cover_candidates._fetch_thalia_page_sync", fake_fetch)
    monkeypatch.setattr("app.routers.cover_candidates.is_safe_cover_import_url", lambda url: False)

    async def run() -> None:
        candidate = await _probe_thalia_candidate("9783426440087", None, 1000, 10)
        assert candidate.available is False
        assert candidate.url == ""

    asyncio.run(run())


# ── _probe_source_candidates direct tests ─────────────────────────────────────


def test_probe_source_candidates_empty_urls() -> None:
    import asyncio
    import pytest
    from app.routers.cover_candidates import _probe_source_candidates

    async def run() -> None:
        with pytest.raises(IndexError):
            await _probe_source_candidates("abebooks", [], None, 1000)

    asyncio.run(run())
