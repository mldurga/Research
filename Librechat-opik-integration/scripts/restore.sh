#!/bin/bash
#
# Restore Script for Self-Hosted Opik + LibreChat
# This script restores databases from backups
#

set -e

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
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup-timestamp>"
    echo ""
    echo "Example: $0 20250123_140530"
    echo ""
    echo "Available backups:"
    ls -1 "${BACKUP_PATH:-/opt/librechat-opik/backups}"/mysql/*.sql.gz | xargs -n1 basename | sed 's/opik-mysql-/  /' | sed 's/.sql.gz//'
    exit 1
fi

TIMESTAMP=$1
BACKUP_DIR="${BACKUP_PATH:-/opt/librechat-opik/backups}"

# Verify backup files exist
if [ ! -f "${BACKUP_DIR}/mysql/opik-mysql-${TIMESTAMP}.sql.gz" ]; then
    error "MySQL backup not found: opik-mysql-${TIMESTAMP}.sql.gz"
fi

if [ ! -f "${BACKUP_DIR}/mongodb/librechat-mongodb-${TIMESTAMP}.archive.gz" ]; then
    error "MongoDB backup not found: librechat-mongodb-${TIMESTAMP}.archive.gz"
fi

# ===================================
# Confirmation
# ===================================

warn "⚠️  WARNING: This will OVERWRITE all current data!"
warn "Backup timestamp: ${TIMESTAMP}"
warn ""
read -p "Are you sure you want to restore? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    log "Restore cancelled"
    exit 0
fi

log "Starting restore process..."

# ===================================
# Stop Services
# ===================================

log "Stopping services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile opik --profile librechat \
    stop librechat-backend opik-backend opik-frontend

log "✓ Services stopped"

# ===================================
# Restore MySQL
# ===================================

log "Restoring MySQL..."
gunzip < "${BACKUP_DIR}/mysql/opik-mysql-${TIMESTAMP}.sql.gz" | \
    docker exec -i opik-mysql mysql \
    -u root \
    -p"${MYSQL_ROOT_PASSWORD}"

if [ $? -eq 0 ]; then
    log "✓ MySQL restored"
else
    error "MySQL restore failed"
fi

# ===================================
# Restore MongoDB
# ===================================

log "Restoring MongoDB..."
docker exec -i librechat-mongodb mongorestore \
    --username="${MONGO_USERNAME}" \
    --password="${MONGO_ROOT_PASSWORD}" \
    --authenticationDatabase=admin \
    --archive \
    --gzip \
    --drop \
    < "${BACKUP_DIR}/mongodb/librechat-mongodb-${TIMESTAMP}.archive.gz"

if [ $? -eq 0 ]; then
    log "✓ MongoDB restored"
else
    error "MongoDB restore failed"
fi

# ===================================
# Restore ClickHouse (optional)
# ===================================

log "Restoring ClickHouse..."
for backup_file in "${BACKUP_DIR}"/clickhouse/*-${TIMESTAMP}.tsv.gz; do
    if [ -f "$backup_file" ]; then
        db=$(basename "$backup_file" | sed "s/-${TIMESTAMP}.tsv.gz//")
        log "  Restoring database: $db"

        # Note: This is a simplified restore. Production should use proper ClickHouse backup tools.
        gunzip < "$backup_file" | \
            docker exec -i opik-clickhouse clickhouse-client \
            --password="${CLICKHOUSE_PASSWORD}" \
            --query="INSERT INTO $db FORMAT TabSeparatedWithNamesAndTypes"
    fi
done

log "✓ ClickHouse restored"

# ===================================
# Restore Redis (optional)
# ===================================

if [ -f "${BACKUP_DIR}/redis/opik-redis-${TIMESTAMP}.rdb" ]; then
    log "Restoring Redis..."

    docker compose -f docker-compose.yml -f docker-compose.prod.yml \
        --profile opik \
        stop opik-redis

    docker cp "${BACKUP_DIR}/redis/opik-redis-${TIMESTAMP}.rdb" \
        opik-redis:/data/dump.rdb

    docker compose -f docker-compose.yml -f docker-compose.prod.yml \
        --profile opik \
        start opik-redis

    log "✓ Redis restored"
fi

# ===================================
# Start Services
# ===================================

log "Starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --profile opik --profile librechat \
    start

log "Waiting for services to be healthy..."
sleep 10

# ===================================
# Verify Restore
# ===================================

log "Verifying restore..."

# Check MySQL
mysql_check=$(docker exec opik-mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SHOW DATABASES;" 2>/dev/null | grep opik || true)
if [ -n "$mysql_check" ]; then
    log "✓ MySQL verification passed"
else
    warn "MySQL verification failed - check manually"
fi

# Check MongoDB
mongo_check=$(docker exec librechat-mongodb mongosh -u "${MONGO_USERNAME}" -p "${MONGO_ROOT_PASSWORD}" --authenticationDatabase admin --eval "db.adminCommand({listDatabases: 1})" 2>/dev/null | grep LibreChat || true)
if [ -n "$mongo_check" ]; then
    log "✓ MongoDB verification passed"
else
    warn "MongoDB verification failed - check manually"
fi

# ===================================
# Summary
# ===================================

log ""
log "==================================="
log "Restore Summary"
log "==================================="
log "Restored from: ${TIMESTAMP}"
log "Services restarted: ✓"
log ""
log "✓ Restore completed successfully!"
log ""
log "Next steps:"
log "  1. Verify LibreChat: http://localhost:3080"
log "  2. Verify Opik: http://localhost:5173"
log "  3. Check logs: docker compose logs -f"
