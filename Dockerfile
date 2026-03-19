# Makestack Shell — Production Docker image
#
# Multi-stage build:
#   1. frontend-build — Node.js builds the React frontend
#   2. runtime       — Python serves the full stack (API + frontend)
#
# The final image contains:
#   - The compiled frontend at /app/frontend/dist/
#   - The Python backend at /app/backend/
#   - The MCP server at /app/mcp_server/
#   - The CLI at /app/cli/
#
# FastAPI serves the frontend via StaticFiles (mounted after all API routes).

# ---------------------------------------------------------------------------
# Stage 1 — Build the React frontend
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Copy dependency manifests first for better layer caching.
COPY frontend/package*.json ./
RUN npm ci --prefer-offline

# Copy source.
COPY frontend/ ./

# Reset auto-generated module files — local dev files reference absolute paths
# outside the build context. Modules are installed at runtime via the package manager.
RUN cp src/modules/registry.template.ts src/modules/registry.ts && \
    sed -i "/'@.*-frontend':/d" vite.config.ts

RUN npm run build
# Result: /app/frontend/dist/


# ---------------------------------------------------------------------------
# Stage 2 — Python runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# System deps needed at runtime (git for package cache ops).
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY backend/ ./backend/
COPY mcp_server/ ./mcp_server/
COPY cli/ ./cli/
COPY makestack_sdk/ ./makestack_sdk/

# Copy the compiled frontend from stage 1.
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create a non-root user to run the application.
RUN groupadd -r makestack && useradd -r -g makestack -d /home/makestack makestack
RUN mkdir -p /home/makestack/.makestack && chown -R makestack:makestack /home/makestack

USER makestack

EXPOSE 3000

# Healthcheck — polls the Shell's own status endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/api/status')" || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "3000"]
