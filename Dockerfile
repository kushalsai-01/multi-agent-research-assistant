# ==============================================================================
# Stage 1: Builder
# Installs dependencies using uv and CPU-only PyTorch to avoid massive CUDA wheels
# ==============================================================================
FROM python:3.11-slim AS builder

# Install uv from the official Astral image for high-speed package resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements
COPY requirements.txt .

# 1. Force CPU-only PyTorch first (reduces bundle from ~5.6 GB CUDA wheels down to ~200 MB)
RUN uv pip install --system --no-cache \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# 2. Install remaining project dependencies
RUN uv pip install --system --no-cache -r requirements.txt


# ==============================================================================
# Stage 2: Final Runtime
# Ultra-lightweight runtime container with non-root user
# ==============================================================================
FROM python:3.11-slim AS runner

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DEPLOYMENT_ENV=production

WORKDIR /app

# Copy installed Python packages and binaries from the builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create a non-root system user for security
RUN useradd -u 1001 -m -s /bin/sh appuser

# Copy application source code
COPY --chown=appuser:appuser agents/ ./agents/
COPY --chown=appuser:appuser api/ ./api/
COPY --chown=appuser:appuser tools/ ./tools/
COPY --chown=appuser:appuser docs/ ./docs/
COPY --chown=appuser:appuser config.py database.py memory.py rag.py ./

# Prepare ephemeral data directory for local fallback
RUN mkdir -p /app/data/qdrant && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

# Run uvicorn bound to the port provided by Render ($PORT) or fallback to 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
