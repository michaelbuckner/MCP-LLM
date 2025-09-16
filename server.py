# server.py
import os
from typing import Optional, Dict, Any
import secrets
import hashlib

from fastmcp import FastMCP, Context, settings
from mcp import ServerSession

# OpenAI client (async)
from openai import AsyncOpenAI

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

# Add authentication middleware for HTTP transports
async def auth_middleware(request, call_next):
    """Middleware to authenticate MCP client requests."""
    # Check if this is an HTTP request with headers
    if hasattr(request, 'headers'):
        # Check Authorization header
        auth_header = request.headers.get('authorization', '') or request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]  # Remove 'Bearer ' prefix
            if verify_api_key(api_key):
                return await call_next(request)
        
        # Check X-API-Key header as alternative
        api_key = request.headers.get('x-api-key', '') or request.headers.get('X-API-Key', '')
        if api_key and verify_api_key(api_key):
            return await call_next(request)
        
        # Return 401 Unauthorized if no valid API key
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    # For non-HTTP transports (like stdio), allow through
    return await call_next(request)

# Add the middleware to the server
mcp.add_middleware(auth_middleware)

# Allow host/port to be configured via env without needing custom ASGI glue.
# (Default mount paths: SSE at /sse, Streamable HTTP at /mcp)
settings.host = os.getenv("HOST", "0.0.0.0")
settings.port = int(os.getenv("PORT", "8000"))

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
    if ctx:
        await ctx.info(f"Dispatching prompt to OpenAI with model={model}")

    # Use Chat Completions for widest compatibility
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        **(extra or {}),
    )
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    finish = choice.finish_reason or "stop"

    return {"text": text, "model": model, "finish_reason": finish}

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
    # Streamable HTTP is the modern, scalable HTTP transport; SSE is still supported.
    mcp.run(transport=args.transport, stateless_http=True)
