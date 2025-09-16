FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY server.py .

# Expose the default port
EXPOSE 8000

# Set environment variables with defaults
ENV HOST=0.0.0.0
ENV PORT=8000
ENV MCP_TRANSPORT=streamable-http
ENV OPENAI_MODEL=gpt-4o-mini
ENV OPENAI_TEMPERATURE=0.2

# Run the server
CMD ["python", "server.py"]
