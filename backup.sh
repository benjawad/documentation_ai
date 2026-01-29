#!/bin/bash
# Database Backup Script
# Works on Linux/Mac. For Windows, run in Git Bash or WSL
# Or use: docker-compose exec db pg_dump -U postgres ai_analyst > backup.sql

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "Starting database backup..."

# Create backup directory
mkdir -p $BACKUP_DIR

# Run pg_dump
docker-compose exec -T db pg_dump -U ${POSTGRES_USER:-postgres} ${POSTGRES_DB:-ai_analyst} > $BACKUP_FILE

# Compress
gzip $BACKUP_FILE

echo "Backup completed: ${BACKUP_FILE}.gz"

# Clean old backups (30 days)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete 2>/dev/null || true

echo "Old backups cleaned"
