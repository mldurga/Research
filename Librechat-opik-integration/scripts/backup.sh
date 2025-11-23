#!/bin/bash
#
# Automated Backup Script for Self-Hosted Opik + LibreChat
# This script backs up all databases and configurations
#

set -e

# Configuration
BACKUP_DIR="${BACKUP_PATH:-/opt/librechat-opik/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Create backup directories
mkdir -p "${BACKUP_DIR}"/{mysql,mongodb,clickhouse,redis,configs}

log "Starting backup process..."

# ===================================
# Backup MySQL (Opik metadata)
# ===================================

log "Backing up MySQL (Opik metadata)..."
docker exec opik-mysql mysqldump \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}" \
    --all-databases \
    --single-transaction \
    --quick \
    --lock-tables=false \
    | gzip > "${BACKUP_DIR}/mysql/opik-mysql-${TIMESTAMP}.sql.gz"

if [ $? -eq 0 ]; then
    log "✓ MySQL backup completed"
else
    error "MySQL backup failed"
    exit 1
fi

# ===================================
# Backup MongoDB (LibreChat data)
# ===================================

log "Backing up MongoDB (LibreChat data)..."
docker exec librechat-mongodb mongodump \
    --username="${MONGO_USERNAME}" \
    --password="${MONGO_ROOT_PASSWORD}" \
    --authenticationDatabase=admin \
    --archive \
    --gzip \
    > "${BACKUP_DIR}/mongodb/librechat-mongodb-${TIMESTAMP}.archive.gz"

if [ $? -eq 0 ]; then
    log "✓ MongoDB backup completed"
else
    error "MongoDB backup failed"
    exit 1
fi

# ===================================
# Backup ClickHouse (Opik analytics)
# ===================================

log "Backing up ClickHouse (Opik analytics)..."

# Get list of databases
databases=$(docker exec opik-clickhouse clickhouse-client -q "SHOW DATABASES" | grep -v -E "^(system|information_schema|INFORMATION_SCHEMA)$")

for db in $databases; do
    log "  Backing up database: $db"
    docker exec opik-clickhouse clickhouse-client \
        --password="${CLICKHOUSE_PASSWORD}" \
        --query="SELECT * FROM $db FORMAT TabSeparatedWithNamesAndTypes" \
        | gzip > "${BACKUP_DIR}/clickhouse/${db}-${TIMESTAMP}.tsv.gz"
done

log "✓ ClickHouse backup completed"

# ===================================
# Backup Redis (Opik cache)
# ===================================

log "Backing up Redis (Opik cache)..."
docker exec opik-redis redis-cli \
    --pass "${REDIS_PASSWORD}" \
    SAVE

# Copy RDB file
docker cp opik-redis:/data/dump.rdb \
    "${BACKUP_DIR}/redis/opik-redis-${TIMESTAMP}.rdb"

if [ $? -eq 0 ]; then
    log "✓ Redis backup completed"
else
    warn "Redis backup failed (cache data, not critical)"
fi

# ===================================
# Backup Configuration Files
# ===================================

log "Backing up configuration files..."

# Copy .env file (without sensitive data in filename)
if [ -f .env.production ]; then
    cp .env.production "${BACKUP_DIR}/configs/env-${TIMESTAMP}.backup"
fi

# Copy docker-compose files
cp docker-compose.yml "${BACKUP_DIR}/configs/docker-compose-${TIMESTAMP}.yml"
cp docker-compose.prod.yml "${BACKUP_DIR}/configs/docker-compose-prod-${TIMESTAMP}.yml"

log "✓ Configuration backup completed"

# ===================================
# Cleanup Old Backups
# ===================================

log "Cleaning up backups older than ${RETENTION_DAYS} days..."

find "${BACKUP_DIR}" -type f -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -type f -name "*.archive.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -type f -name "*.tsv.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -type f -name "*.rdb" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}/configs" -type f -mtime +${RETENTION_DAYS} -delete

log "✓ Old backups cleaned up"

# ===================================
# Backup Summary
# ===================================

log ""
log "==================================="
log "Backup Summary"
log "==================================="
log "Timestamp: ${TIMESTAMP}"
log "Backup directory: ${BACKUP_DIR}"
log ""

# Calculate sizes
mysql_size=$(du -sh "${BACKUP_DIR}/mysql/opik-mysql-${TIMESTAMP}.sql.gz" | cut -f1)
mongodb_size=$(du -sh "${BACKUP_DIR}/mongodb/librechat-mongodb-${TIMESTAMP}.archive.gz" | cut -f1)
total_size=$(du -sh "${BACKUP_DIR}" | cut -f1)

log "MySQL backup: ${mysql_size}"
log "MongoDB backup: ${mongodb_size}"
log "Total backup size: ${total_size}"
log ""
log "✓ Backup completed successfully!"

# ===================================
# Optional: Upload to Remote Storage
# ===================================

# Uncomment to enable S3 upload
# if [ -n "${S3_BACKUP_BUCKET}" ]; then
#     log "Uploading to S3: ${S3_BACKUP_BUCKET}"
#     aws s3 sync "${BACKUP_DIR}" "s3://${S3_BACKUP_BUCKET}/backups/$(date +%Y/%m/%d)/" \
#         --exclude "*.tmp" \
#         --storage-class STANDARD_IA
#     log "✓ S3 upload completed"
# fi

# Uncomment to enable remote rsync
# if [ -n "${BACKUP_REMOTE_HOST}" ]; then
#     log "Syncing to remote host: ${BACKUP_REMOTE_HOST}"
#     rsync -avz --delete \
#         "${BACKUP_DIR}/" \
#         "${BACKUP_REMOTE_USER}@${BACKUP_REMOTE_HOST}:${BACKUP_REMOTE_PATH}/"
#     log "✓ Remote sync completed"
# fi
