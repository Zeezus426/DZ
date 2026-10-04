# Multi-stage build for production Docker image

# ---------------------------------------------------------------------------
# Stage 1: Build stage — install deps and collect static files
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings \
    DJANGO_SETTINGS_ENV=prod

# Build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Virtual environment keeps the runtime copy small and self-contained
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (cached layer). uv for fast installs.
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache -r /tmp/requirements.txt

WORKDIR /app
COPY . /app/

# Dummy database credentials so importing prod settings during the build can
# never attempt a real connection. collectstatic does not touch the DB, but a
# missing DB_* var would otherwise silently fall back to the base defaults.
ENV SECRET_KEY=build-time-dummy-key-not-used-at-runtime \
    DB_HOST=localhost \
    DB_PORT=5432 \
    DB_NAME=dummy \
    DB_USER=dummy \
    DB_PASSWORD=dummy

# Build the hashed/compressed static manifest
RUN python manage.py collectstatic --noinput --clear


# ---------------------------------------------------------------------------
# Stage 2: Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings \
    DJANGO_SETTINGS_ENV=prod

# Runtime dependencies: libpq5 for psycopg, postgresql-client for pg_dump/psql,
# curl for the health check.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy project files
COPY --chown=appuser:appuser . /app/

# Copy collected static files from the builder (overwrites any local staticfiles)
COPY --from=builder --chown=appuser:appuser /app/staticfiles /app/staticfiles

# Writable directories for logs (prod.py FileHandler) and media uploads
RUN mkdir -p /app/logs /app/media && \
    chown -R appuser:appuser /app/logs /app/media

USER appuser

EXPOSE 8000

# Health check. SECURE_SSL_REDIRECT returns a 301 on plain HTTP, which `curl -f`
# treats as success — enough to prove the WSGI app is up and serving.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run migrations on deploy, then start Gunicorn with logs on stdout/stderr
CMD sh -c "python manage.py migrate --noinput && \
    exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -"
