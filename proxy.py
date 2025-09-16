import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import StreamingResponse

# --- Configuration ---
TARGET_HOST = os.environ.get("TARGET_HOST", "http://localhost:8000")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8001"))
MCP_API_KEY = os.environ.get("MCP_API_KEY")

app = FastAPI()

@app.post("/mcp")
async def mcp_proxy(request: Request):
    """
    A proxy endpoint that accepts non-compliant MCP requests,
    fixes the headers, and forwards them to the actual MCP server.
    """
    try:
        # Extract the body and headers from the incoming request
        body = await request.body()
        headers = dict(request.headers)

        # --- Header Correction ---
        # Forcefully set the correct Accept header
        headers["accept"] = "application/json, text/event-stream"
        # Ensure the host header is correct for the target service
        headers["host"] = "localhost:8000"

        # --- Forward the Request ---
        async with httpx.AsyncClient() as client:
            # Stream the request to the target server
            mcp_request = client.build_request(
                "POST",
                f"{TARGET_HOST}/mcp",
                content=body,
                headers=headers,
            )
            mcp_response = await client.send(mcp_request, stream=True)

            # --- Stream the Response Back ---
            return StreamingResponse(
                mcp_response.aiter_bytes(),
                status_code=mcp_response.status_code,
                headers=mcp_response.headers,
            )

    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)
