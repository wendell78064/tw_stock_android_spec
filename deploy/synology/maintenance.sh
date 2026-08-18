#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

export PATH="${PATH}:/usr/local/bin:/var/packages/ContainerManager/target/usr/bin:/volume1/@appstore/ContainerManager/usr/bin"

DATA_ROOT="${TWML_DATA_ROOT:-/volume1/docker/tw-market-ledger}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-twml-postgres}"
PG_USER="${POSTGRES_USER:-twstock}"
PG_DB="${POSTGRES_DB:-twstock}"

echo "========================================================================"
echo " TW Market Ledger - Storage & Maintenance Report"
echo " Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "========================================================================"

# 1. Volume Disk Usage Check & Alert
echo -e "\n--- [1] Volume Storage Usage ---"
VOLUME_LINE=$(df -h /volume1 | awk 'NR==2')
echo "${VOLUME_LINE}"
USAGE_PCT=$(echo "${VOLUME_LINE}" | awk '{print $5}' | tr -d '%')

if [ "${USAGE_PCT}" -ge 85 ]; then
  echo ">>> [CRITICAL] Storage usage is at ${USAGE_PCT}% (>= 85%)! Immediate cleanup required! <<<"
elif [ "${USAGE_PCT}" -ge 75 ]; then
  echo ">>> [WARNING] Storage usage is at ${USAGE_PCT}% (>= 75%). Monitor disk growth closely. <<<"
else
  echo "Storage usage status: NORMAL (${USAGE_PCT}% used)"
fi

# 2. Directory Usage Breakdown
echo -e "\n--- [2] TW Market Ledger Directory Usage ---"
if [ -d "${DATA_ROOT}" ]; then
  du -sh "${DATA_ROOT}"/* 2>/dev/null || echo "No subdirectories found"
else
  echo "Directory ${DATA_ROOT} does not exist."
fi

# 3. Docker Disk Usage
echo -e "\n--- [3] Docker Resource Utilization ---"
docker system df 2>/dev/null || echo "Docker daemon not accessible"

# 4. PostgreSQL Database & Table Sizes
echo -e "\n--- [4] PostgreSQL Database & Growth Table Sizes ---"
if docker ps --format '{{.Names}}' | grep -qw "${POSTGRES_CONTAINER}"; then
  docker exec "${POSTGRES_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -c "
    SELECT pg_size_pretty(pg_database_size('${PG_DB}')) AS total_database_size;
  " 2>/dev/null || true

  echo "Top Non-canonical / High-Growth Tables:"
  docker exec "${POSTGRES_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -c "
    SELECT
      relname AS table_name,
      pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
      n_live_tup AS estimated_live_rows
    FROM pg_stat_user_tables
    ORDER BY pg_total_relation_size(relid) DESC
    LIMIT 10;
  " 2>/dev/null || true
else
  echo "Postgres container is not running."
fi

# 5. Clean Expired Temp Files (> 24 hours)
echo -e "\n--- [5] Cleaning Expired Temp Artifacts ---"
TEMP_DIR="${DATA_ROOT}/temp"
if [ -d "${TEMP_DIR}" ]; then
  CLEANED_COUNT=$(find "${TEMP_DIR}" -type f -mtime +1 -delete -print 2>/dev/null | wc -l || echo "0")
  echo "Cleaned ${CLEANED_COUNT} expired temp/report/export files (>24 hours old)."
fi

# 6. Optional Table Retention Compaction
if [ "${1:-}" = "--purge-retention" ]; then
  echo -e "\n--- [6] Executing Table Retention Policy Purge ---"
  if docker ps --format '{{.Names}}' | grep -qw "${POSTGRES_CONTAINER}"; then
    docker exec "${POSTGRES_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -c "
      -- Sync Changes retention (~90 days)
      DELETE FROM sync_changes WHERE changed_at < NOW() - INTERVAL '90 days';
      -- Sync Operations retention (~90 days)
      DELETE FROM sync_operations WHERE created_at < NOW() - INTERVAL '90 days';
      -- Ingestion Runs audit retention (~180 days)
      DELETE FROM ingestion_runs WHERE started_at < NOW() - INTERVAL '180 days';
      -- Alert Events history retention (~365 days / 1 year)
      DELETE FROM alert_events WHERE triggered_at < NOW() - INTERVAL '365 days';
      -- Vacuum analyze to reclaim space
      VACUUM ANALYZE;
    "
    echo "Purge and VACUUM ANALYZE completed."
  fi
else
  echo -e "\n--- [6] Retention Policy ---"
  echo "To purge noncanonical tables (sync changes > 90d, ingestion > 180d, alerts > 365d), run:"
  echo "  ./maintenance.sh --purge-retention"
fi

echo -e "\n========================================================================"
echo " Maintenance Check Completed."
echo "========================================================================"
