# TW Market Ledger - Synology DS220+ Production Deployment

This package provides deployment scripts, production Docker compose manifests, backup/restore procedures, and storage guard maintenance for Synology DS220+ NAS (Intel Celeron J4025, 2 cores, 6 GB RAM, DSM Container Manager).

## Optional Sinopac Shioaji realtime provider

The backend remains healthy with the provider unconfigured. A human administrator must later
create a Sinopac API key and secret with market-data-only capability, then store them only in the
production environment:

```dotenv
REALTIME_PROVIDER=shioaji
SHIOAJI_API_KEY=<secret>
SHIOAJI_SECRET_KEY=<secret>
SHIOAJI_SIMULATION=false
```

Never commit these values, place them in Android, persist them in the database, or emit them to
logs. No CA activation, account access, or trading permission is used. Before broader
subscriptions, perform one production smoke with a single stock's Tick and BidAsk streams.

The restricted administrator wrapper must expose only these fixed commands (the wrapper's shared
`DOCKER` variable is reused):

```sh
smoke-realtime-tick|smoke-realtime-bidask)
  MARKET="${2:-}"
  CODE="${3:-}"
  case "$MARKET" in TWSE|TPEX) ;; *) exit 2 ;; esac
  case "$CODE" in
    [0-9][0-9][0-9][0-9]|[0-9][0-9][0-9][0-9][0-9]|[0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) exit 2 ;;
  esac
  if [ "$1" = "smoke-realtime-tick" ]; then QUOTE_TYPE=tick; else QUOTE_TYPE=bidask; fi
  "$DOCKER" exec -i twml-backend python -m app.cli.smoke_realtime_quote \
    --market "$MARKET" --code "$CODE" --quote-type "$QUOTE_TYPE" --timeout 10
  ;;
```

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
- **Backend**: Memory limit: `1536M`, Memory reservation: `256M`
- **PostgreSQL**: Memory limit: `1024M`, Memory reservation: `256M`
- **Redis**: Memory limit: `384M`, Memory reservation: `64M`
- **Total Peak Memory Budget**: ~2.9 GB (leaves >3 GB for DSM system and existing containers). Note: `cpus` limits are omitted for native Synology Docker kernel compatibility (no CFS quota dependency).

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

### Step 1: Container Registry (GHCR) Access
Production images are built via GitHub Actions and published to GitHub Container Registry:
`ghcr.io/wendell78064/tw_stock_android_spec-backend:<tag>`

- **Option A (Public Package)**: If the package visibility is set to Public under GitHub Repository / Package Settings, no `docker login` is needed on the NAS.
- **Option B (Private Package)**: Log in once on NAS using a Personal Access Token (`read:packages` scope):
  ```bash
  echo "<YOUR_GITHUB_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
  ```

### Step 2: Prepare Environment File
```bash
cp .env.example .env
# Edit .env and supply strong secrets for AUTH_SECRET, ADMIN_API_KEY, and POSTGRES_PASSWORD
# Optionally pin BACKEND_IMAGE tag (e.g., BACKEND_IMAGE=ghcr.io/wendell78064/tw_stock_android_spec-backend:sha-82b02c2)
```

### Step 3: Deploy Services
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
- **Atomic Creation & Verification**: Uses temporary file + `gzip -t` verification before atomic move; file mode `600`.
- **Ownership & Mode Alignment**: Automatically aligns permissions with parent `backups/` directory (mode `2770`, deploy user ownership).
- **Count-Bounded GFS Retention**:
  - **Daily retention**: Newest 7 backups (`Daily <= 7`)
  - **Weekly retention**: Newest 4 backups (`Weekly <= 4`)
  - **Monthly retention**: Newest 12 backups (`Monthly <= 12`)

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

## 6. Cloudflare Tunnel & Public Ingress Operations

### Architecture & Routing
- **Public Hostname**: `stock-api.orca-wave.com`
- **Cloudflare Tunnel Name**: `wendell-ds220`
- **Production Origin Service**: `http://twml-backend:8000`

### Standalone `cloudflared` Container & Network Attachment
The `cloudflared` daemon is **not** managed by the TWML Docker Compose stack; it runs as an existing standalone Synology Container Manager container.

To route public traffic securely to the isolated TWML stack without opening inbound ports on the router:
1. Connect `cloudflared` to the isolated stack network:
   ```bash
   docker network connect twml-network cloudflared
   ```
2. `cloudflared` must be attached to both networks:
   - `bridge` (for public Cloudflare edge outbound connectivity)
   - `twml-network` (for internal communication with `twml-backend`)

### Attachment Persistence Behavior
- **Container restarts**: Normal restart of `cloudflared` preserves the `twml-network` attachment.
- **Docker / Container Manager daemon restarts**: Preserves the network attachment.
- **NAS reboots**: Preserves the network attachment.
- **Container recreation**: If the `cloudflared` container is deleted and recreated, the `docker network connect twml-network cloudflared` command **must be re-executed manually**.

### Network Verification Command
```bash
docker inspect cloudflared \
  --format '{{range $name, $conf := .NetworkSettings.Networks}}{{$name}} {{end}}'
```
**Expected Output**:
```text
bridge twml-network
```

### Cloudflare Tunnel Ingress Configuration
In Cloudflare Zero Trust Dashboard (or `config.yml` for tunnel `wendell-ds220`):
- **Hostname**: `stock-api.orca-wave.com`
- **Service**: `http://twml-backend:8000`

### Production External Health Endpoints
- `https://stock-api.orca-wave.com/v1/health`
- `https://stock-api.orca-wave.com/v1/ready`
- `https://stock-api.orca-wave.com/v1/production-readiness`

### Security Posture & Exposure Policy
- **Zero Port Forwarding**: Never expose Synology DSM, PostgreSQL (`5432`), Redis (`6379`), or raw backend port (`8000`) publicly on the router/WAN.
- All public client and Android app requests enter exclusively via HTTPS through Cloudflare Tunnel edge.

---

## 7. Production Runtime Verification Baseline

As of Step 15 deployment verification on Synology DS220+:
- **`/v1/health`**: HTTP `200 OK` (`{"status": "ok"}`)
- **`/v1/ready`**: HTTP `200 OK` (`ready: true`, `postgres: ok`, `redis: ok`)
- **`/v1/production-readiness`**: HTTP `200 OK` (`status: "HEALTHY"`, `ready: true`)
- **External Gate Gating**:
  - `ai_provider`: `UNCONFIGURED` (by design)
  - `push_provider`: `UNCONFIGURED` (by design)
  - `realtime_provider`: `UNCONFIGURED` (by design)
- **Database Migrations**: PostgreSQL head is verified at `0014_personal_data_sync`.
- **Redis Memory Policy**: `maxmemory 256mb`, `volatile-lru`.
- **Storage Guard**: Daily backup verified with count-bounded GFS retention and mode `2770`/`600`.
