#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# --- 1. Wait for Database (All Containers) ---
echo "🚀 Checking Database Connection..."
while ! </dev/tcp/db/5432; do
  echo "⏳ Waiting for Postgres..."
  sleep 1
done
echo "✅ Database is up!"

# --- 2. Wait for Redis (All Containers) ---
# Celery worker needs this immediately. Web needs it for caching/queueing.
echo "🚀 Checking Redis Connection..."
while ! </dev/tcp/redis/6379; do
  echo "⏳ Waiting for Redis..."
  sleep 1
done
echo "✅ Redis is up!"

# --- 3. Run Maintenance Tasks (Web Container Only) ---
# We check if the command passed ($1) contains "celery".
# If it is NOT celery, we assume it's the web server, so we run migrations.
if [[ "$1" != *"celery"* ]]; then
    echo "📦 Applying Database Migrations..."
    python manage.py migrate --noinput

    echo "🎨 Collecting Static Files..."
    python manage.py collectstatic --noinput
else
    echo "👷 Starting Celery Worker... (Skipping migrations)"
fi

echo "🔥 Starting Command: $@"
exec "$@"