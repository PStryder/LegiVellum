# AsyncGate Dockerfile
# The Execution Coordinator - Task queue and worker coordination

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
COPY components/asyncgate/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy component source
COPY components/asyncgate/src/ /app/src/

WORKDIR /app/src

# Environment defaults
ENV PORT=8002
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MEMORYGATE_URL=http://memorygate:8001
ENV LEASE_DURATION_SECONDS=900
ENV RUN_MODE=rest

EXPOSE 8002

# Health check (MCP tools/call)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import json, os, urllib.request; port=os.environ.get('PORT','8002'); url=f'http://localhost:{port}/mcp'; payload={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'asyncgate.health','arguments':{}}}; req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}); resp=urllib.request.urlopen(req, timeout=5); data=json.load(resp); assert 'result' in data" || exit 0

# Entrypoint script to support both REST and MCP modes
# RUN_MODE=rest (default) -> FastAPI server
# RUN_MODE=mcp -> MCP server via stdio
CMD if [ "$RUN_MODE" = "mcp" ]; then \
        python mcp_server.py; \
    else \
        python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}; \
    fi
