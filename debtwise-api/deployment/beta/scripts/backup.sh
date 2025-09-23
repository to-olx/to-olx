#!/bin/bash
# Database backup script for DebtWise Beta

set -e

# Configuration
BACKUP_DIR="/backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="debtwise_beta_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=7

echo "[$(date)] Starting database backup..."

# Create backup
pg_dump --verbose --no-owner --no-acl | gzip > "$BACKUP_DIR/$BACKUP_FILE"

echo "[$(date)] Backup created: $BACKUP_FILE"

# Upload to S3 if configured
if [ ! -z "$AWS_S3_BUCKET" ]; then
    echo "[$(date)] Uploading to S3..."
    aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "s3://$AWS_S3_BUCKET/db-backups/$BACKUP_FILE"
    echo "[$(date)] Upload complete"
fi

# Clean up old backups
echo "[$(date)] Cleaning up old backups..."
find "$BACKUP_DIR" -name "debtwise_beta_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup process completed"