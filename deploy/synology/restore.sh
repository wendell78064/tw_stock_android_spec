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

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-backup-file.sql.gz>"
  echo "Example: $0 /volume1/docker/tw-market-ledger/backups/daily/twstock_20260818_120000.sql.gz"
  exit 1
fi

RESTORE_FILE="$1"

if [ ! -f "${RESTORE_FILE}" ]; then
  echo "Error: Backup file '${RESTORE_FILE}' does not exist."
  exit 1
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-twml-postgres}"
PG_USER="${POSTGRES_USER:-twstock}"
PG_DB="${POSTGRES_DB:-twstock}"

echo "========================================================================"
echo " [RESTORE CONFIRMATION REQUIRED]"
echo " Target Database:   ${PG_DB}"
echo " Container:         ${POSTGRES_CONTAINER}"
echo " Backup Source:     ${RESTORE_FILE}"
echo " Size:              $(du -h "${RESTORE_FILE}" | cut -f1)"
echo " WARNING: This operation will OVERWRITE existing data in ${PG_DB}!"
echo "========================================================================"
printf "Type 'RESTORE-CONFIRM' to proceed: "
read -r CONFIRMATION

if [ "${CONFIRMATION}" != "RESTORE-CONFIRM" ]; then
  echo "Restore aborted by user."
  exit 1
fi

echo "==> Restoring database from ${RESTORE_FILE}..."
gunzip -c "${RESTORE_FILE}" | docker exec -i "${POSTGRES_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}"

echo "==> Database restore completed successfully."
