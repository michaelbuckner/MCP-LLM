# MCP Server Error Fixes

## Issues Resolved

### ClosedResourceError noise
Non-compliant MCP HTTP clients would fail the Accept negotiation, trigger a 406 response, and tear down the stream. The resulting disconnect bubbled up as `anyio.ClosedResourceError`, cluttering the logs.

### Missing health endpoint
Container health checks expected `/health` to respond with 200s, but the default FastMCP app did not ship that route.

## Key Changes

- Introduced a dedicated Starlette middleware stack:
  - `ErrorHandlingMiddleware` converts disconnects into 499 responses and shields unexpected exceptions with a JSON 500.
  - `AuthMiddleware` enforces bearer or `X-API-Key` authentication on `/mcp` and `/sse`, while allowing `/` and `/health` probes.
  - `ForceAcceptHeaderMiddleware` rewrites `/mcp` requests to advertise both `application/json` and `text/event-stream`, satisfying the MCP transport requirements for legacy clients.
- Registered the middleware with `FastMCP.run_async(..., middleware=HTTP_MIDDLEWARE)` so every HTTP transport benefits from the fixes.
- Added a lightweight `/health` route via `FastMCP.custom_route` for container orchestration.

## Operational Notes

- The middleware stack only runs for HTTP/SSE transports; stdio mode remains unchanged.
- Authentication still hashes the configured API key and compares with constant-time checks.
- Logging now captures disconnects at INFO level instead of surfacing full stack traces.

## Testing

- `pytest` (unit tests for authentication, binding, and Accept-header handling)
