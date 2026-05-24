# syntax=docker/dockerfile:1

# ── Stage 1: build deps ────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Install system dependencies for psycopg2-binary build
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy lockfile + project manifest first for layer caching
COPY pyproject.toml uv.lock ./

# Install all deps including postgres extra into the project venv
RUN uv sync --frozen --no-dev --extra postgres

# ── Stage 2: runtime ───────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

WORKDIR /app

# libpq is needed at runtime by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd --gid 1001 cantica && \
    useradd --uid 1001 --gid cantica --shell /bin/bash --create-home cantica

# Copy the installed venv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/ src/
COPY pyproject.toml ./

# Data volume — prompts and SQLite DB live here unless DATABASE_URL is set
RUN mkdir -p /data && chown cantica:cantica /data
VOLUME ["/data"]

USER cantica

ENV CANTICA_VAULT_PATH=/data \
    CANTICA_HOST=0.0.0.0 \
    CANTICA_PORT=8042 \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8042

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8042/health || exit 1

CMD ["cantica", "serve", "--host", "0.0.0.0", "--port", "8042"]
