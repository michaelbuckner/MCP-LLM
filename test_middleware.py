import asyncio
import base64
import os
from starlette.requests import Request
from starlette.responses import Response

# Ensure required environment variables exist before importing the server
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-middleware")
os.environ.setdefault("MCP_API_KEY", "test-mcp-key-123")

from server import AuthMiddleware, ForceAcceptHeaderMiddleware


async def empty_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def build_scope(headers=None, path="/mcp", query_string: str | bytes = b""):
    if isinstance(query_string, str):
        query_bytes = query_string.encode()
    else:
        query_bytes = query_string
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
        "query_string": query_bytes,
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


def run_auth_middleware(headers=None, path="/mcp", query_string=""):
    async def runner():
        scope = build_scope(headers=headers, path=path, query_string=query_string)
        request = Request(scope, empty_receive)
        middleware = AuthMiddleware(app=lambda scope, receive, send: None)
        state = {"called": False}

        async def call_next(req):
            state["called"] = True
            return Response(status_code=204)

        response = await middleware.dispatch(request, call_next)
        return state["called"], response

    return asyncio.run(runner())


def test_auth_middleware_accepts_bearer_header():
    headers = [(b"authorization", b"Bearer test-mcp-key-123")]
    called, response = run_auth_middleware(headers=headers)
    assert called is True
    assert response.status_code == 204


def test_auth_middleware_accepts_basic_header():
    token = base64.b64encode(b"test-mcp-key-123:").decode("ascii")
    headers = [(b"authorization", f"Basic {token}".encode("ascii"))]
    called, response = run_auth_middleware(headers=headers)
    assert called is True
    assert response.status_code == 204


def test_auth_middleware_accepts_query_parameter():
    called, response = run_auth_middleware(query_string="api_key=test-mcp-key-123")
    assert called is True
    assert response.status_code == 204


def test_auth_middleware_rejects_missing_credentials():
    called, response = run_auth_middleware(headers=[])
    assert called is False
    assert response.status_code == 401


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
