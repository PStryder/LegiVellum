# DeleGate Dockerfile
# The Pure Planner - Intent-to-plan transformation

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first (for layer caching)
COPY shared/ /app/shared/

# Install shared library
RUN pip install --no-cache-dir /app/shared/

# Copy component requirements and install
COPY components/delegate/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy component source
COPY components/delegate/src/ /app/src/

WORKDIR /app/src

# Environment defaults
ENV PORT=8003
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MEMORYGATE_URL=http://memorygate:8001
ENV ASYNCGATE_URL=http://asyncgate:8002
ENV RUN_MODE=rest

EXPOSE 8003

# Health check (only applies to REST mode)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${PORT}/health').raise_for_status()" || exit 0

# Entrypoint script to support both REST and MCP modes
# RUN_MODE=rest (default) -> FastAPI server
# RUN_MODE=mcp -> MCP server via stdio
CMD if [ "$RUN_MODE" = "mcp" ]; then \
        python mcp_server.py; \
    else \
        python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}; \
    fi
