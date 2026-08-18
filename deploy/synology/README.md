# TW Market Ledger - Synology DS220+ Production Deployment

This package provides deployment scripts, production Docker compose manifests, backup/restore procedures, and storage guard maintenance for Synology DS220+ NAS (Intel Celeron J4025, 2 cores, 6 GB RAM, DSM Container Manager).

## 1. Directory Structure

On Synology DS220+, all persistent TWML data is isolated under:
```text
/volume1/docker/tw-market-ledger/
├── postgres/          # PostgreSQL 16 database cluster data
├── redis/             # Redis 7 AOF and state persistence
├── backups/           # GFS database backup archives (daily/weekly/monthly)
├── config/            # Local configuration mounts
└── temp/              # Temporary artifacts (CSV preview, PDF reports, export files)
```

## 2. Architecture & Networking

- **Isolated Docker Network**: `twml-network` (bridge).
- **Internal Service Communication**:
  - Backend: `http://backend:8000` (or container alias `twml-backend`)
  - PostgreSQL: `postgres:5432` (internal only, not bound to host)
  - Redis: `redis:6379` (internal only, not bound to host)
- **Zero Public Port Exposure**: PostgreSQL and Redis ports are never published to host or WAN.
- **Cloudflare Tunnel Routing**: The existing `cloudflared` container on the NAS can connect to `twml-network` and route ingress to `http://backend:8000` or `http://twml-backend:8000`.

## 3. Resource Limits & Storage Guard

### DS220+ Resource Allocation
- **Backend**: CPU limit: `1.50`, Memory limit: `1536M`, Memory reservation: `256M`
- **PostgreSQL**: CPU limit: `1.00`, Memory limit: `1024M`, Memory reservation: `256M`
- **Redis**: CPU limit: `0.50`, Memory limit: `384M`, Memory reservation: `64M`
- **Total Peak Memory Budget**: ~2.9 GB (leaves >3 GB for DSM system and existing containers).

### Log Rotation & Realtime Logs
- Bounded container log rotation: `max-size: 20m`, `max-file: 5` across all services.
- Realtime quote ingestion uses structured INFO/DEBUG logs without per-tick spam.

### Redis Maxmemory & Eviction
- `maxmemory 256mb`
- `maxmemory-policy volatile-lru` (protects persistent keys while cleanly expiring transient caches).

### PostgreSQL Non-canonical Retention
- Non-canonical high-growth tables:
  - `sync_changes` & `sync_operations`: 90-day retention
  - `ingestion_runs`: 180-day retention
  - `alert_events`: 365-day (1-year) retention
- Canonical daily price history, securities taxonomy, and user portfolio transactions are preserved indefinitely.

## 4. Deployment Instructions

### Step 1: Prepare Environment File
```bash
cp .env.example .env
# Edit .env and supply strong secrets for AUTH_SECRET, ADMIN_API_KEY, and POSTGRES_PASSWORD
```

### Step 2: Deploy Services
```bash
chmod +x deploy.sh backup.sh restore.sh maintenance.sh
./deploy.sh
```

### Step 3: Verify Health
```bash
docker exec -t twml-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/v1/health').read().decode())"
docker exec -t twml-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/v1/ready').read().decode())"
docker exec -t twml-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/v1/production-readiness').read().decode())"
```

## 5. Operations & Maintenance

### Automated Backups
Schedule `deploy/synology/backup.sh` via DSM Task Scheduler (Task Scheduler -> User-defined script -> daily run as root or docker user).
- **Daily retention**: 7 days
- **Weekly retention**: 4 weeks
- **Monthly retention**: 12 months

### Safe Restore
```bash
./restore.sh /volume1/docker/tw-market-ledger/backups/daily/twstock_YYYYMMDD_HHMMSS.sql.gz
# Explicit confirmation 'RESTORE-CONFIRM' is required.
```

### Storage Monitoring & Temp Cleanup
Run `deploy/synology/maintenance.sh` periodically to inspect volume usage, PostgreSQL table sizes, and clean expired temp files.
- Warning alert triggered at $\ge 75\%$ disk usage.
- Critical alert triggered at $\ge 85\%$ disk usage.
- To execute non-canonical table pruning: `./maintenance.sh --purge-retention`.

## 6. Cloudflare Tunnel Integration

To route `stock-api.orca-wave.com` to TWML backend:
1. Connect the existing `cloudflared` container to `twml-network`:
   ```bash
   docker network connect twml-network cloudflared
   ```
2. Configure Cloudflare Tunnel ingress rule:
   - Hostname: `stock-api.orca-wave.com`
   - Service: `http://backend:8000` (or `http://twml-backend:8000`)
