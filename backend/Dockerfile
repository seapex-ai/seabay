FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
# Copy a minimal app package so hatchling can build, then install deps
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
RUN pip install --no-cache-dir .

# ── Runtime stage ──
FROM python:3.12-slim

WORKDIR /app

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Ensure app module is importable
ENV PYTHONPATH=/app

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create non-root user
RUN groupadd -r seabay && useradd -r -g seabay seabay
USER seabay

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# Run migrations then start uvicorn
CMD ["./entrypoint.sh"]
