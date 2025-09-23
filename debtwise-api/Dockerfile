# Use official Python runtime as base image
FROM python:3.13-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .python-version ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Development stage
FROM base AS development

# Install dev dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

# Change ownership to app user
RUN chown -R app:app /app

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uv", "run", "python", "main.py"]

# Production stage
FROM base AS production

# Copy application code
COPY --chown=app:app . .

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Command to run the application with production server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]