# OpenAI MCP Relay Server

A Model Context Protocol (MCP) server that relays prompts to OpenAI's API and returns responses. This server can be easily deployed using Docker.

## Features

- Single-tool MCP server for OpenAI API integration
- **API key authentication** for secure client access
- Supports multiple transport protocols (streamable-http, SSE, stdio)
- Configurable via environment variables
- Docker containerized for easy deployment
- Health check endpoint for monitoring

## Prerequisites

- Docker and Docker Compose
- OpenAI API key

## Quick Start

### Using Docker Compose (Recommended)

1. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

2. Run the server:
   ```bash
   docker-compose up -d
   ```

3. The server will be available at `http://localhost:8000`

### Using Docker directly

1. Build the image:
   ```bash
   docker build -t openai-mcp-server .
   ```

2. Run the container:
   ```bash
   docker run -d \
     -p 8000:8000 \
     -e OPENAI_API_KEY="your-api-key-here" \
     --name openai-mcp-server \
     openai-mcp-server
   ```

## Configuration

The server can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) | - |
| `OPENAI_BASE_URL` | Custom OpenAI API base URL | - |
| `OPENAI_MODEL` | Default OpenAI model to use | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Default temperature for responses | `0.2` |
| `MCP_API_KEY` | API key for MCP client authentication (optional) | Auto-generated |
| `HOST` | Server host address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `MCP_TRANSPORT` | Transport protocol | `streamable-http` |

## API Endpoints

### MCP Endpoints
- **Streamable HTTP**: `http://localhost:8000/mcp`
- **Server-Sent Events**: `http://localhost:8000/sse`

### Tool: `generate`

Sends a prompt to OpenAI and returns the response.

**Parameters:**
- `prompt` (string, required): The text prompt to send to OpenAI
- `model` (string, optional): OpenAI model name (defaults to env `OPENAI_MODEL`)
- `temperature` (float, optional): Sampling temperature (defaults to env `OPENAI_TEMPERATURE`)
- `max_tokens` (integer, optional): Maximum output tokens
- `extra` (object, optional): Additional parameters to forward to OpenAI API

**Returns:**
```json
{
  "text": "Generated response text",
  "model": "gpt-4o-mini",
  "finish_reason": "stop"
}
```

## Development

### Running locally without Docker

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. Run the server:
   ```bash
   python server.py
   ```

### Transport Options

The server supports multiple transport protocols:

- `streamable-http` (default): Modern HTTP transport
- `sse`: Server-Sent Events transport
- `stdio`: Standard input/output transport

Change the transport by setting the `MCP_TRANSPORT` environment variable or using the `--transport` command line argument.

## Authentication

The server supports API key authentication for MCP clients connecting via HTTP transports (streamable-http and SSE). Authentication is automatically bypassed for stdio transport (local connections).

### Setting up Authentication

1. **Auto-generated API Key** (Default):
   If no `MCP_API_KEY` is set, the server will generate a random API key on startup and display it in the logs:
   ```
   Generated MCP API Key: abc123def456...
   Set MCP_API_KEY environment variable to use a custom key.
   ```

2. **Custom API Key**:
   Set your own API key using the environment variable:
   ```bash
   export MCP_API_KEY="your-custom-api-key-here"
   ```

### Client Authentication

MCP clients must include the API key in their requests using one of these methods:

1. **Authorization Header** (Recommended):
   ```
   Authorization: Bearer your-api-key-here
   ```

2. **X-API-Key Header**:
   ```
   X-API-Key: your-api-key-here
   ```

### Example Client Configuration

When configuring your MCP client, include the authentication headers:

```json
{
  "mcpServers": {
    "openai-relay": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Authorization: Bearer your-api-key-here",
        "-H", "Content-Type: application/json",
        "http://localhost:8000/mcp"
      ]
    }
  }
}
```

### Security Notes

- API keys are hashed using SHA-256 for secure storage and comparison
- Authentication is enforced for all HTTP-based transports
- Local stdio connections bypass authentication for development convenience
- Use strong, unique API keys in production environments

## Health Check

The server includes a health check endpoint for monitoring (when using docker-compose):
- **Endpoint**: `http://localhost:8000/health`
- **Interval**: Every 30 seconds
- **Timeout**: 10 seconds

## Logs

To view logs when running with Docker Compose:
```bash
docker-compose logs -f openai-mcp-server
```

## Stopping the Server

### Docker Compose
```bash
docker-compose down
```

### Docker
```bash
docker stop openai-mcp-server
docker rm openai-mcp-server
```

## Troubleshooting

1. **Server won't start**: Check that your `OPENAI_API_KEY` is set correctly
2. **Connection refused**: Ensure the port 8000 is not being used by another service
3. **API errors**: Verify your OpenAI API key has sufficient credits and permissions
4. **Docker/Cloud deployment issues**: 
   - The server binds to `0.0.0.0` by default for container compatibility
   - For local development, you can override with `HOST=127.0.0.1`
   - Ensure your cloud platform allows the configured port (default: 8000)
5. **Authentication failures**: 
   - Check that the `Authorization: Bearer <key>` or `X-API-Key: <key>` header is included
   - Verify the API key matches the one displayed in server logs or set via `MCP_API_KEY`

## License

This project is provided as-is for educational and development purposes.
