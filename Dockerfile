# Stage 1: Builder
FROM python:3.11-slim-bookworm as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages directly (no venv needed in Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Final (minimal runtime)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder (only site-packages, not entire /usr/local)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# SAFE ENTRYPOINT LOCATION (Fixes "no such file" error)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY mcp_entrypoint.sh /usr/local/bin/mcp_entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/mcp_entrypoint.sh

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
