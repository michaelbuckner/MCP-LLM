# server.py
import os
from typing import Optional, Dict, Any
import secrets
import hashlib
import asyncio
import logging
import signal
import sys

from fastmcp import FastMCP, Context, settings
from mcp import ServerSession

# OpenAI client (async)
from openai import AsyncOpenAI

# Import Request for middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
# HTTP utilities
# (FastAPI fully re-exports Starlette responses, so stick to Starlette primitives)

# Import anyio for proper error handling
import anyio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Config ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in your environment.")

# Optional: override API base (e.g., Azure OpenAI or a proxy)
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")  # e.g., "https://api.openai.com/v1"

# MCP Server Authentication
MCP_API_KEY = os.environ.get("MCP_API_KEY")
if not MCP_API_KEY:
    # Generate a random API key if none is provided
    MCP_API_KEY = secrets.token_urlsafe(32)
    print(f"Generated MCP API Key: {MCP_API_KEY}")
    print("Set MCP_API_KEY environment variable to use a custom key.")

# Hash the API key for secure comparison
MCP_API_KEY_HASH = hashlib.sha256(MCP_API_KEY.encode()).hexdigest()

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# Authentication function
def verify_api_key(provided_key: str) -> bool:
    """Verify the provided API key against the configured key."""
    if not provided_key:
        return False
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return secrets.compare_digest(provided_hash, MCP_API_KEY_HASH)

# Create the MCP server
mcp = FastMCP(
    name="openai-relay",
    instructions="A single-tool server that relays prompts to OpenAI and returns the response."
)


# --- HTTP middleware for compatibility and robustness ---

class ForceAcceptHeaderMiddleware(BaseHTTPMiddleware):
    """Ensure POST /mcp requests advertise the media types required by MCP."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.scope.get("type") == "http" and request.url.path == "/mcp":
            headers = MutableHeaders(scope=request.scope)
            accept_header = headers.get("accept", "")
            accept_values = [value.strip() for value in accept_header.split(",") if value.strip()]
            normalized = {value.lower() for value in accept_values}

            updated = False
            if "application/json" not in normalized:
                accept_values.append("application/json")
                updated = True
            if "text/event-stream" not in normalized:
                accept_values.append("text/event-stream")
                updated = True

            if updated:
                headers["accept"] = ", ".join(accept_values)
                logger.debug("Adjusted Accept header for /mcp request: %s", headers["accept"])

        return await call_next(request)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Convert transport exceptions into friendly HTTP responses."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        try:
            return await call_next(request)
        except anyio.ClosedResourceError:
            logger.info("Client disconnected - ClosedResourceError handled by middleware")
            return PlainTextResponse("Client disconnected", status_code=499)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error in request processing: %s", exc, exc_info=True)
            return JSONResponse(
                content={"error": "Internal server error", "detail": str(exc)},
                status_code=500,
            )


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate HTTP requests hitting MCP endpoints."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.scope.get("type") != "http":
            return await call_next(request)

        if request.url.path in {"/health", "/"}:
            return await call_next(request)

        # Only enforce auth for MCP HTTP transports
        if request.url.path not in {"/mcp", "/sse"}:
            return await call_next(request)

        # Authorization: Bearer <token>
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
            if verify_api_key(api_key):
                return await call_next(request)

        # Alternative header
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        if api_key and verify_api_key(api_key):
            return await call_next(request)

        logger.warning("Unauthorized access attempt to %s", request.url.path)
        return JSONResponse(
            {"error": "Invalid or missing API key"},
            status_code=401,
        )


# Allow host/port to be configured via env without needing custom ASGI glue.
# (Default mount paths: SSE at /sse, Streamable HTTP at /mcp)
settings.host = os.getenv("HOST", "0.0.0.0")
settings.port = int(os.getenv("PORT", "8000"))


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Simple health check used by container orchestration."""
    return JSONResponse({"status": "ok"})

# Note: FastMCP handles routing internally for MCP endpoints
# Health check and root endpoints will be handled by the error middleware
# if they return 404, which is acceptable for an MCP server

@mcp.tool()
async def generate(
    prompt: str,
    model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    temperature: float = float(os.environ.get("OPENAI_TEMPERATURE", "0.2")),
    max_tokens: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    ctx: Optional[Context] = None,
) -> Dict[str, Any]:
    """
    Send a prompt to the OpenAI API and return the response text.
    Arguments:
      - prompt: user text to send
      - model: OpenAI model name (default: env OPENAI_MODEL or gpt-4o-mini)
      - temperature: sampling temperature
      - max_tokens: optional max output tokens
      - extra: optional dict forwarded to OpenAI (e.g., top_p, presence_penalty)
    Returns:
      { "text": str, "model": str, "finish_reason": str }
    """
    try:
        if ctx:
            await ctx.info(f"Dispatching prompt to OpenAI with model={model}")

        # Validate input parameters
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        if temperature < 0 or temperature > 2:
            raise ValueError("Temperature must be between 0 and 2")
        
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        # Use Chat Completions for widest compatibility
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **(extra or {}),
        )
        
        if not resp.choices:
            raise RuntimeError("No response choices returned from OpenAI")
        
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        finish = choice.finish_reason or "stop"

        if ctx:
            await ctx.info(f"Successfully generated response with finish_reason: {finish}")

        return {"text": text, "model": model, "finish_reason": finish}
    
    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        logger.error(error_msg)
        
        if ctx:
            await ctx.error(error_msg)
        
        # Return error information instead of raising to prevent stream disconnection
        return {
            "text": f"Error: {str(e)}",
            "model": model,
            "finish_reason": "error",
            "error": True
        }

HTTP_MIDDLEWARE = [
    Middleware(ErrorHandlingMiddleware),
    Middleware(AuthMiddleware),
    Middleware(ForceAcceptHeaderMiddleware),
]


async def run_server_with_error_handling(transport, host, port):
    """Run the MCP server with comprehensive error handling for ClosedResourceError."""
    try:
        logger.info(f"Starting MCP server on {host}:{port} with transport {transport}")
        
        transport_kwargs = {}
        if transport in {"http", "streamable-http", "sse"}:
            transport_kwargs.update(
                {
                    "stateless_http": True,
                    "host": host,
                    "port": port,
                    "middleware": HTTP_MIDDLEWARE,
                }
            )

        # Run the server with error handling
        await mcp.run_async(
            transport=transport,
            **transport_kwargs,
        )
    except anyio.ClosedResourceError:
        logger.info("Client disconnected - ClosedResourceError caught at server level")
        # Don't re-raise, just log and continue
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected server error: {str(e)}")
        # For other errors, we might want to restart or exit gracefully
        raise

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenAI MCP Relay Server")
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default=os.getenv("MCP_TRANSPORT", "streamable-http"),
        help="Transport protocol for the MCP server.",
    )
    args = parser.parse_args()
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    # Check if FastMCP supports async run
    if hasattr(mcp, 'run_async'):
        # Use async version with error handling
        try:
            asyncio.run(run_server_with_error_handling(args.transport, host, port))
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server failed to start: {e}")
            sys.exit(1)
    else:
        # Fallback to synchronous version
        try:
            logger.info(f"Starting MCP server on {host}:{port} with transport {args.transport}")
            mcp.run(
                transport=args.transport, 
                stateless_http=True,
                host=host,
                port=port
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            # Don't exit on ClosedResourceError, just log it
            if "ClosedResourceError" not in str(e):
                sys.exit(1)
