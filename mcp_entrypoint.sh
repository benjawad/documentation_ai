#!/bin/bash
# MCP Server entrypoint script

set -e

echo "🔧 MCP Server - Starting..."

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "✅ PostgreSQL is ready!"

# Wait for Redis
echo "⏳ Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo "✅ Redis is ready!"

# Apply database migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Start MCP server
echo "🚀 Starting MCP Server..."
exec python /app/core/services/small_mcp.py
