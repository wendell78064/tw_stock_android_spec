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
mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly" "${BACKUP_DIR}/monthly"

# 1. Ownership & Permissions Alignment
# If executed under sudo or root, inherit owner:group from BACKUP_DIR or fallback to SUDO_USER
TARGET_UID="$(stat -c '%u' "${BACKUP_DIR}" 2>/dev/null || echo "")"
TARGET_GID="$(stat -c '%g' "${BACKUP_DIR}" 2>/dev/null || echo "")"

if [ -z "${TARGET_UID}" ] || [ "${TARGET_UID}" -eq 0 ]; then
  if [ -n "${SUDO_USER:-}" ] && id -u "${SUDO_USER}" &>/dev/null; then
    TARGET_UID="$(id -u "${SUDO_USER}")"
    TARGET_GID="$(id -g "${SUDO_USER}")"
  fi
fi

if [ -n "${TARGET_UID}" ] && [ "${TARGET_UID}" -ne 0 ] 2>/dev/null; then
  chown "${TARGET_UID}:${TARGET_GID}" "${BACKUP_DIR}" "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly" "${BACKUP_DIR}/monthly" 2>/dev/null || true
fi

chmod 2770 "${BACKUP_DIR}" "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly" "${BACKUP_DIR}/monthly" 2>/dev/null || true

DATE_TAG="$(date +%Y%m%d_%H%M%S)"
DAY_OF_WEEK="$(date +%u)" # 1=Mon .. 7=Sun
DAY_OF_MONTH="$(date +%d)"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-twml-postgres}"
PG_USER="${POSTGRES_USER:-twstock}"
PG_DB="${POSTGRES_DB:-twstock}"

FINAL_BACKUP_FILE="${BACKUP_DIR}/daily/twstock_${DATE_TAG}.sql.gz"
TEMP_BACKUP_FILE="${BACKUP_DIR}/daily/.twstock_${DATE_TAG}.sql.gz.tmp.$$"

# Clean up partial temp file on unexpected exit or error
trap 'rm -f "${TEMP_BACKUP_FILE}"' EXIT INT TERM

echo "==> Creating atomic PostgreSQL database backup to ${FINAL_BACKUP_FILE}..."
docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${PG_USER}" "${PG_DB}" | gzip -9 > "${TEMP_BACKUP_FILE}"

# 2. Validation & Integrity Check
if [ ! -s "${TEMP_BACKUP_FILE}" ]; then
  echo "Error: Backup file is empty or pg_dump failed."
  exit 1
fi

if ! gzip -t "${TEMP_BACKUP_FILE}" 2>/dev/null; then
  echo "Error: Gzip integrity check failed for temporary backup."
  exit 1
fi

# Set restrictive mode 600 and target ownership before moving into final location
chmod 600 "${TEMP_BACKUP_FILE}"
if [ -n "${TARGET_UID}" ] && [ "${TARGET_UID}" -ne 0 ] 2>/dev/null; then
  chown "${TARGET_UID}:${TARGET_GID}" "${TEMP_BACKUP_FILE}" 2>/dev/null || true
fi

# Atomic move to final backup path
mv "${TEMP_BACKUP_FILE}" "${FINAL_BACKUP_FILE}"
trap - EXIT INT TERM

echo "==> Backup successfully created and verified ($(du -h "${FINAL_BACKUP_FILE}" | cut -f1))."

# 3. Weekly snapshot (Sunday = 7)
if [ "${DAY_OF_WEEK}" -eq 7 ]; then
  WEEKLY_FILE="${BACKUP_DIR}/weekly/twstock_weekly_${DATE_TAG}.sql.gz"
  cp -p "${FINAL_BACKUP_FILE}" "${WEEKLY_FILE}"
  echo "==> Weekly snapshot archived: ${WEEKLY_FILE}"
fi

# 4. Monthly snapshot (1st day of month)
if [ "${DAY_OF_MONTH}" = "01" ]; then
  MONTHLY_FILE="${BACKUP_DIR}/monthly/twstock_monthly_${DATE_TAG}.sql.gz"
  cp -p "${FINAL_BACKUP_FILE}" "${MONTHLY_FILE}"
  echo "==> Monthly snapshot archived: ${MONTHLY_FILE}"
fi

# 5. Count-Bounded GFS Retention Pruning
# Helper function: keep newest N files matching pattern, delete older ones
prune_count_bounded() {
  local target_dir="$1"
  local file_pattern="$2"
  local keep_count="$3"

  if [ -d "${target_dir}" ]; then
    # Sort matching files newest first (by modification time or filename timestamp)
    mapfile -t ALL_FILES < <(find "${target_dir}" -maxdepth 1 -type f -name "${file_pattern}" 2>/dev/null | sort -r)
    local total="${#ALL_FILES[@]}"
    if [ "${total}" -gt "${keep_count}" ]; then
      for ((i=keep_count; i<total; i++)); do
        rm -f "${ALL_FILES[i]}"
      done
    fi
  fi
}

echo "==> Pruning old backups based on count-bounded GFS retention (Keep newest: Daily <= 7, Weekly <= 4, Monthly <= 12)..."
prune_count_bounded "${BACKUP_DIR}/daily" "twstock_*.sql.gz" 7
prune_count_bounded "${BACKUP_DIR}/weekly" "twstock_weekly_*.sql.gz" 4
prune_count_bounded "${BACKUP_DIR}/monthly" "twstock_monthly_*.sql.gz" 12

echo "==> Backup and retention pruning completed."
