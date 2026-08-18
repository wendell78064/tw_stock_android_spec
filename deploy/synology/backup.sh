#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Safely extract specific non-secret operational variables from .env without sourcing arbitrary shell code
if [ -f .env ]; then
  TWML_DATA_ROOT="${TWML_DATA_ROOT:-$(grep -E '^TWML_DATA_ROOT=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- | tr -d '"'\''')}"
  POSTGRES_USER="${POSTGRES_USER:-$(grep -E '^POSTGRES_USER=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- | tr -d '"'\''')}"
  POSTGRES_DB="${POSTGRES_DB:-$(grep -E '^POSTGRES_DB=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- | tr -d '"'\''')}"
fi

export PATH="${PATH}:/usr/local/bin:/var/packages/ContainerManager/target/usr/bin:/volume1/@appstore/ContainerManager/usr/bin"

BACKUP_DIR="${TWML_DATA_ROOT:-/volume1/docker/tw-market-ledger}/backups"
mkdir -p "${BACKUP_DIR}/daily"
mkdir -p "${BACKUP_DIR}/weekly"
mkdir -p "${BACKUP_DIR}/monthly"

DATE_TAG="$(date +%Y%m%d_%H%M%S)"
DAY_OF_WEEK="$(date +%u)" # 1=Mon .. 7=Sun
DAY_OF_MONTH="$(date +%d)"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-twml-postgres}"
PG_USER="${POSTGRES_USER:-twstock}"
PG_DB="${POSTGRES_DB:-twstock}"

BACKUP_FILE="${BACKUP_DIR}/daily/twstock_${DATE_TAG}.sql.gz"

echo "==> Creating PostgreSQL database backup to ${BACKUP_FILE}..."
docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${PG_USER}" "${PG_DB}" | gzip -9 > "${BACKUP_FILE}"

if [ ! -s "${BACKUP_FILE}" ]; then
  echo "Error: Backup file is empty or failed to generate."
  rm -f "${BACKUP_FILE}"
  exit 1
fi

echo "==> Backup successfully created ($(du -h "${BACKUP_FILE}" | cut -f1))."

# Weekly rotation (Sunday = 7)
if [ "${DAY_OF_WEEK}" -eq 7 ]; then
  WEEKLY_FILE="${BACKUP_DIR}/weekly/twstock_weekly_${DATE_TAG}.sql.gz"
  cp "${BACKUP_FILE}" "${WEEKLY_FILE}"
  echo "==> Weekly snapshot archived: ${WEEKLY_FILE}"
fi

# Monthly rotation (1st day of month)
if [ "${DAY_OF_MONTH}" = "01" ]; then
  MONTHLY_FILE="${BACKUP_DIR}/monthly/twstock_monthly_${DATE_TAG}.sql.gz"
  cp "${BACKUP_FILE}" "${MONTHLY_FILE}"
  echo "==> Monthly snapshot archived: ${MONTHLY_FILE}"
fi

echo "==> Pruning old backups based on GFS retention policy (Daily: 7, Weekly: 4, Monthly: 12)..."
# Daily: Keep 7 days
find "${BACKUP_DIR}/daily" -name "twstock_*.sql.gz" -type f -mtime +7 -delete 2>/dev/null || true
# Weekly: Keep 4 weeks (~28 days)
find "${BACKUP_DIR}/weekly" -name "twstock_weekly_*.sql.gz" -type f -mtime +28 -delete 2>/dev/null || true
# Monthly: Keep 12 months (~365 days)
find "${BACKUP_DIR}/monthly" -name "twstock_monthly_*.sql.gz" -type f -mtime +365 -delete 2>/dev/null || true

echo "==> Backup and retention pruning completed."
