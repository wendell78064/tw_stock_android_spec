#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ ! -f .env ]; then
  echo "Error: .env file not found in ${SCRIPT_DIR}."
  echo "Please copy .env.example to .env and configure the required production secrets."
  exit 1
fi

export PATH="${PATH}:/usr/local/bin:/var/packages/ContainerManager/target/usr/bin:/volume1/@appstore/ContainerManager/usr/bin"

DATA_ROOT="${TWML_DATA_ROOT:-/volume1/docker/tw-market-ledger}"
echo "==> Ensuring required persistent directories exist under ${DATA_ROOT}..."
mkdir -p "${DATA_ROOT}/postgres"
mkdir -p "${DATA_ROOT}/redis"
mkdir -p "${DATA_ROOT}/backups"
mkdir -p "${DATA_ROOT}/config"
mkdir -p "${DATA_ROOT}/temp"

echo "==> Deploying TW Market Ledger services with Docker Compose..."
if command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
elif docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
else
  echo "Error: Neither docker compose nor docker-compose found in PATH."
  exit 1
fi

${COMPOSE_CMD} up -d --build

echo "==> Waiting for postgres service to become healthy..."
${COMPOSE_CMD} exec -T postgres sh -c 'until pg_isready -U "${POSTGRES_USER:-twstock}" -d "${POSTGRES_DB:-twstock}"; do sleep 1; done'

echo "==> Waiting for backend service to finish migrations and become healthy..."
MAX_ATTEMPTS=30
ATTEMPT=0
UNTIL_HEALTHY=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  STATUS=$(${COMPOSE_CMD} ps backend --format '{{.Status}}' 2>/dev/null || echo "")
  if echo "${STATUS}" | grep -qi "(healthy)"; then
    UNTIL_HEALTHY=1
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  sleep 2
done

if [ $UNTIL_HEALTHY -eq 1 ]; then
  echo "==> TW Market Ledger backend is UP and HEALTHY."
else
  echo "Warning: Backend service has not yet reported (healthy) after 60s. Check logs with: ${COMPOSE_CMD} logs -n 50 backend"
fi

echo "==> Verifying Alembic current migration head..."
${COMPOSE_CMD} exec -T backend alembic current

echo "==> Deployment process completed."
