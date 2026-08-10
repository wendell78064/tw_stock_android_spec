# 台股持股與市場籌碼 Android App 規格包

本規格包用於指導 AI 或開發團隊建立一套涵蓋台股現貨、台指期貨、法人籌碼、信用交易、產業強弱、持股管理及提醒功能的 Android App。

## 建議閱讀順序

1. `AGENTS.md`：AI 開發總規則。
2. `docs/00_MASTER_PRD.md`：完整產品需求。
3. `docs/01_APP_SCREEN_FLOW.md`：App 畫面與操作流程。
4. `docs/02_DATABASE_ERD.md`：資料庫 ERD 與欄位規則。
5. `docs/03_BACKEND_API_SPEC.md`：後端 REST／WebSocket API 規格。
6. `docs/04_DEVELOPMENT_ROADMAP.md`：分階段開發任務與驗收條件。
7. `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`：資料來源、更新時序與授權注意事項。
8. `api/openapi.yaml`：可供產生 Client／Server 型別的 OpenAPI 契約草案。
9. `db/schema.sql`：核心 PostgreSQL schema 起始版本。

## 建議專案結構

```text
tw-stock-app/
├── AGENTS.md
├── README.md
├── android-app/
├── backend/
├── api/
│   └── openapi.yaml
├── db/
│   └── schema.sql
├── docs/
└── infra/
```

## 建議技術棧

### Android

- Kotlin
- Jetpack Compose + Material 3
- Navigation Compose
- MVVM + Repository
- Hilt
- Retrofit 或 Ktor Client
- Kotlin Coroutines / Flow
- Room
- DataStore
- WorkManager
- Firebase Cloud Messaging
- MPAndroidChart、Vico 或 Compose 原生圖表元件；正式採用前需驗證 K 線、縮放與效能

### Backend

- Python 3.12+
- FastAPI
- Pydantic 2
- SQLAlchemy 2
- Alembic
- PostgreSQL 16
- TimescaleDB：進入分鐘行情後啟用
- Redis
- APScheduler、ARQ 或 Celery：依部署規模選擇
- WebSocket
- Pytest
- Docker Compose

## 重要範圍限制

- 投資組合交易輸入只有：股票代號、買進／賣出、日期時間、股數、成交價格、手續費、零股／整股。
- 不建立股利、除權息、減資、增資等投資組合事件輸入功能。
- 圖表仍可使用還原權息價格，以避免長期技術分析失真；這屬行情資料處理，不是持股事件管理。
- 盤中即時行情必須透過合法授權來源，不以網頁爬蟲作為正式產品資料源。

## 實作狀態

Phase 0 Monorepo 基礎與 Phase 1 垂直切片 1「股票主檔與搜尋」已完成並保持驗證。Phase 1 垂直切片 2 已加入日 K、日／週／月聚合、RAW／ADJUSTED 邊界、可重現技術指標 API，以及 Android 個股走勢頁。操作與限制請見 [`docs/07_PHASE_1_SECURITY_MASTER.md`](docs/07_PHASE_1_SECURITY_MASTER.md) 與 [`docs/08_PHASE_1_DAILY_PRICES_TECHNICALS.md`](docs/08_PHASE_1_DAILY_PRICES_TECHNICALS.md)。分鐘、即時行情及其他後續功能尚未實作。

快速啟動與固定 Fixture 同步：

```bash
make up
make sync-securities
make backfill-security CODE=1234 MARKET=TWSE FROM=2025-01-01 TO=2026-08-07
curl 'http://localhost:8000/v1/securities/search?q=12'
curl 'http://localhost:8000/v1/securities/1234/candles?market=TWSE&range=1Y&interval=1d&adjustment=ADJUSTED'
```
