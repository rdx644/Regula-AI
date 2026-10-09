import asyncio

from fastapi import Request, Response

from app.core.middleware import RateLimitMiddleware, UploadSizeLimitMiddleware


class FakeRedis:
    def __init__(self, initial=None):
        self.counts = dict(initial or {})

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, _key, _seconds):
        return True


def make_request(path: str) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("198.51.100.10", 12345),
        "server": ("testserver", 80),
    })


def test_rate_limiter_rejects_before_running_endpoint():
    redis = FakeRedis({"regulaai:rate:198.51.100.10:login": 10})
    middleware = RateLimitMiddleware(lambda *_args: None, redis_client=redis)
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("should not run")

    response = asyncio.run(middleware.dispatch(make_request("/api/auth/login/access-token"), call_next))
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert called is False


def test_rate_limiter_fails_closed_without_store_when_required():
    middleware = RateLimitMiddleware(lambda *_args: None, redis_client=None, fail_closed=True)
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("should not run")

    response = asyncio.run(middleware.dispatch(make_request("/api/health"), call_next))
    assert response.status_code == 503
    assert called is False


def test_upload_size_limit_rejects_before_multipart_parsing():
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/api/regulations/1/versions/2/file",
        "raw_path": b"/api/regulations/1/versions/2/file",
        "query_string": b"",
        "headers": [(b"content-length", str(30 * 1024 * 1024).encode())],
        "client": ("198.51.100.10", 12345),
        "server": ("testserver", 80),
    }
    middleware = UploadSizeLimitMiddleware(lambda *_args: None)
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("should not reach multipart parser")

    response = asyncio.run(middleware.dispatch(Request(scope), call_next))
    assert response.status_code == 413
    assert called is False
