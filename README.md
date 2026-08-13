# TW Market Ledger

台股市場分析與個人投資管理系統，包含 FastAPI 後端與 Kotlin／Jetpack Compose Android App。目前已完成 Phase 0～5 軟體功能，以及 Phase 6 / Slice 1 的 Account、Authentication、Cloud Sync Foundation 與 Watchlist 多裝置同步垂直切片。

> 本專案是軟體實作與可重現測試環境，不提供投資建議。正式即時行情仍需合法授權資料供應商。

## Current Status

| 項目 | 狀態 |
|---|---|
| Phase 0～4 | COMPLETE |
| Phase 5 Realtime Software | COMPLETE |
| Phase 6 / Slice 1 Account / Cloud Sync | COMPLETE（CI pending） |
| PostgreSQL | migration `0013_account_sync_foundation` |
| Android Room | version 11 |
| Production Realtime Provider | UNCONFIGURED |
| FCM | UNCONFIGURED |

完整進度請參考 [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)。

## Implemented Features

- 台股證券搜尋、日 K、技術指標與市場總覽
- 三大法人、融資融券與信用交易資料
- TAIFEX 期貨／選擇權、法人 OI、Put/Call、Max Pain 與連續期貨
- 投資組合、損益、交易紀錄與持股分析
- 多群組 Watchlist、排序、備註與目標／停損／加碼價
- 產業／主題分類、強弱排名、Screener 與股票比較
- Realtime WebSocket、盤中報價、1m／5m K、行情廣度與即時提醒
- Android 盤中圖表、即時市場／產業 UI 與提醒介面
- UUID Account、Argon2id 密碼、短效 access token 與 rotating refresh token
- 穩定匿名 Device Identity、使用者隔離與登出快取清除
- Watchlist optimistic concurrency、tombstone、idempotent push、bounded cursor pull 與 bootstrap
- Android Keystore token storage、single-flight refresh、Room durable outbox 與離線同步狀態

## Architecture

```text
Android (Compose / Hilt / Retrofit / Room)
        │ REST + WebSocket
        ▼
FastAPI (Auth / Market / Personal Data / Sync)
        ├── PostgreSQL 16 + Alembic
        └── Redis (realtime cache / Pub/Sub)
```

```text
Account → Device → Authenticated User Scope
        → Durable Outbox → Idempotent Push
        → Version Conflict / Tombstone
        → Incremental Cursor Pull → Device B
```

## Repository Layout

```text
android-app/   Kotlin, Compose, Room, Retrofit, Hilt
backend/       FastAPI, SQLAlchemy, Alembic, Pytest
api/           OpenAPI 3.1 contract
docs/          PRD, architecture, roadmap, slice reports
infra/         infrastructure notes
```

## Quick Start

需求：Docker、Docker Compose，以及 Android 開發時所需的 JDK 17／Android SDK。

```bash
docker compose up --build -d
curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/ready
```

本機 development 會使用 process-local ephemeral auth secret。正式環境必須設定高熵 `AUTH_SECRET`，並由 HTTPS ingress／reverse proxy 終止 TLS；production plaintext HTTP 不受支援。

```bash
export APP_ENV=production
export AUTH_SECRET='<secure deployment secret>'
docker compose up --build -d
```

## Authentication and Sync

主要 endpoint：

```text
POST /v1/auth/register
POST /v1/auth/login
POST /v1/auth/refresh
POST /v1/auth/logout
GET  /v1/me
POST /v1/devices
POST /v1/sync/push
GET  /v1/sync/changes?cursor=0&limit=100
GET  /v1/sync/bootstrap
```

Authenticated identity 只取自 bearer token，客戶端不能用 request body 指定資料擁有者。第一個 cloud-sync vertical slice 僅涵蓋 Watchlist；Portfolio、Alerts、Screeners 與 Settings cloud sync 留待後續 Slice。

舊版未歸屬 Watchlist 不會自動綁定第一位註冊者。管理者可明確執行：

```bash
docker compose run --rm backend \
  python -m app.cli.claim_legacy_personal_data --user <user-uuid>
```

## Validation

Phase 6 / Slice 1 本機結果：

- Ruff: PASS
- Pytest: PASS — 127 tests
- OpenAPI validation / Kotlin generation: PASS
- Android lint and unit tests: PASS
- Debug APK and instrumentation APK: PASS
- Device instrumentation execution: NOT RUN
- Alembic `0012 → 0013 → 0012 → 0013`: PASS
- Room v10 → v11 runtime migration execution: NOT RUN
- Auth、refresh rotation、user isolation、Device A/B sync、conflict、tombstone 與 Watchlist regression smoke: PASS

```bash
make backend-lint
make backend-test
make openapi-validate
make openapi-generate
make android-lint
make android-test
make android-build
make android-ui-test-apk
```

Incremental sync smoke：1,000 change-log entries 在 2.951 秒完成；最後 100 筆增量 pull 為 9.97 ms，回傳維持 bounded 100 rows。數據僅代表本機測試環境。

## Product and Data Boundaries

- 正式即時行情必須使用合法授權 provider，不以網頁爬蟲充當產品資料源。
- FCM 與 production realtime provider 尚未設定。
- 投資組合交易輸入不包含股利、除權息、減資或增資事件。
- 行情圖表可使用還原權息價格；此為市場資料處理，不是持股事件管理。
- Auth endpoint 的 production rate limiting 應由 ingress／API gateway 落實。

## Documentation

- [`docs/00_MASTER_PRD.md`](docs/00_MASTER_PRD.md)
- [`docs/04_DEVELOPMENT_ROADMAP.md`](docs/04_DEVELOPMENT_ROADMAP.md)
- [`docs/05_DATA_SOURCES_AND_COMPLIANCE.md`](docs/05_DATA_SOURCES_AND_COMPLIANCE.md)
- [`docs/21_PHASE_5_REALTIME_ALERT_ENGINE.md`](docs/21_PHASE_5_REALTIME_ALERT_ENGINE.md)
- [`docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md`](docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md)
- [`api/openapi.yaml`](api/openapi.yaml)

## Next

Phase 6 / Slice 2 — Portfolio / Alerts / Screener / Settings Sync（尚未開始）。
