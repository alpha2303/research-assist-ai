# Backend Dockerfile using uv for fast dependency installation
FROM ghcr.io/astral-sh/uv:python3.12-alpine3.23

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# System libraries required by native extensions (PyMuPDF, psycopg2, etc.)
RUN apk add --no-cache libstdc++ libpq

# Install all dependencies including dev tools (watchdog for auto-reload)
# Production builds use Dockerfile.prod with --no-dev
RUN uv sync --frozen

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
# Source - https://stackoverflow.com/a/75871228
# Posted by DRB
# Retrieved 2026-02-16, License - CC BY-SA 4.0

CMD uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

