# Phase 0 — 開發與操作

## 範圍

本階段只建立 Monorepo、Android Compose、FastAPI、PostgreSQL、Redis、Docker Compose、OpenAPI code generation、CI、設定、結構化日誌、健康檢查、Provider 與交易日抽象。未實作 Phase 1 市場功能，Fake Provider 不含真實行情或捏造價格。

## 目錄

```text
android-app/       Kotlin、Compose、Hilt、多模組與本機 API 設定
backend/           FastAPI、SQLAlchemy 2、Alembic、Provider／Calendar abstractions
api/               OpenAPI 契約來源
infra/             後續部署環境設定的保留位置
docs/              規格及操作文件
compose.yaml       Backend、PostgreSQL、Redis 與 Android builder
```

## 啟動與健康檢查

```bash
cp .env.example .env
make up
make health
```

Backend：`http://localhost:8000/v1`。Android Emulator 使用 `http://10.0.2.2:8000/v1/`。

`/v1/health` 只驗證程序存活；`/v1/ready` 實際查詢 PostgreSQL 與 Redis。Compose 會等兩者健康後才啟動 Backend，Backend 啟動時自動執行 `alembic upgrade head`。

## 建置與測試

```bash
make backend-lint
make backend-test
make backend-build
make android-test
make android-build
```

OpenAPI 驗證與 Kotlin client 產生：

```bash
docker compose --profile build run --rm android-builder \
  ./gradlew --no-daemon openApiValidate openApiGenerate
```

產物在 `android-app/build/generated/openapi`，屬建置產物，不提交版本控制；`api/openapi.yaml` 始終是契約來源。

## Migration 驗證

```bash
make migrate-down
make migrate-up
```

正式 schema 的任何後續變更均新增 Alembic revision，不直接修改資料庫。`db/schema.sql` 僅是規格參考。

## 資料與授權邊界

- `MarketDataProvider` 隔離上游格式；`FakeMarketDataProvider` 固定回傳 `UNAVAILABLE`、UTC `as_of`／`received_at` 與缺失原因。
- 金融值使用 Python `Decimal`；API 契約以 decimal string 傳輸。
- `WeekendOnlyCalendar` 僅供 Phase 0 wiring，正式資料前需替換為台灣交易所行事曆 Adapter。
- 不使用網頁爬蟲、不擷取或散布任何真實盤中行情。

