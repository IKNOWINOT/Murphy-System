#!/bin/bash
# Backup Script for Client-Facing Automation System
# Performs database and file backups

set -e

# Configuration
BACKUP_DIR="/workspace/backups"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="automation_platform"
POSTGRES_USER="postgres"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR/database"
mkdir -p "$BACKUP_DIR/files"

echo "Starting backup at $(date)"

# Backup database
echo "Backing up PostgreSQL database..."
pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c -f "$BACKUP_DIR/database/automation_platform_$DATE.dump"

# Backup configuration files
echo "Backing up configuration files..."
tar -czf "$BACKUP_DIR/files/config_$DATE.tar.gz" /workspace/config

# Backup n8n workflows (if they exist)
if [ -d "/workspace/.n8n" ]; then
    echo "Backing up n8n data..."
    tar -czf "$BACKUP_DIR/files/n8n_$DATE.tar.gz" /workspace/.n8n
fi

# Clean up old backups (older than RETENTION_DAYS)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Verify backup
if [ -f "$BACKUP_DIR/database/automation_platform_$DATE.dump" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/database/automation_platform_$DATE.dump" | cut -f1)
    echo "Backup completed successfully! Size: $BACKUP_SIZE"
    echo "Backup file: $BACKUP_DIR/database/automation_platform_$DATE.dump"
else
    echo "ERROR: Backup file not found!"
    exit 1
fi

echo "Backup finished at $(date)"