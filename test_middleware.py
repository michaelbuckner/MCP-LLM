import asyncio
from starlette.requests import Request
from starlette.responses import Response

from server import ForceAcceptHeaderMiddleware


async def empty_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def build_scope(headers=None, path="/mcp"):
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "scheme": "http",
        "headers": headers or [],
        "client": ("test", 12345),
        "server": ("server", 80),
    }


def test_force_accept_header_adds_missing_values():
    async def runner():
        scope = build_scope(headers=[(b"accept", b"application/json")])
        request = Request(scope, empty_receive)
        recorded = {}

        async def call_next(req):
            recorded["accept"] = req.headers.get("accept")
            return Response()

        middleware = ForceAcceptHeaderMiddleware(app=lambda scope, receive, send: None)
        await middleware.dispatch(request, call_next)

        accept_header = recorded["accept"]
        assert "application/json" in accept_header
        assert "text/event-stream" in accept_header

    asyncio.run(runner())


def test_force_accept_header_skips_unrelated_paths():
    async def runner():
        scope = build_scope(headers=[(b"accept", b"application/json")], path="/other")
        request = Request(scope, empty_receive)
        recorded = {}

        async def call_next(req):
            recorded["accept"] = req.headers.get("accept")
            return Response()

        middleware = ForceAcceptHeaderMiddleware(app=lambda scope, receive, send: None)
        await middleware.dispatch(request, call_next)

        assert recorded["accept"] == "application/json"

    asyncio.run(runner())
