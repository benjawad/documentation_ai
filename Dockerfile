# Stage 1: Builder
FROM python:3.13-slim-bookworm as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install requirements into the image (no virtualenv)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/usr/local -r requirements.txt

# Install dev dependencies if in development
COPY requirements-dev.txt .
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
    pip install --no-cache-dir --prefix=/usr/local -r requirements-dev.txt; \
    fi

# Stage 2: Final
FROM python:3.13-slim-bookworm

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

RUN apt-get update && apt-get install -y \
    libpq5 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder into system prefix
COPY --from=builder /usr/local /usr/local

# SAFE ENTRYPOINT LOCATION (Fixes "no such file" error)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app
# Create staticfiles directory with correct permissions
RUN mkdir -p /app/staticfiles && chown -R appuser:appgroup /app

# Copy application code
COPY ./src /app
RUN chown -R appuser:appgroup /app

USER appuser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default Fallback Command
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
