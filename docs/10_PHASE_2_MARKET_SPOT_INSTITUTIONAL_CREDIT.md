# Phase 2／Slice 1：市場現貨、法人與信用交易

## 架構

資料依 `TWSE／TPEx Adapter → MarketSpotProvider → Domain record → dataset-scoped ingestion → PostgreSQL → Repository/Service → REST → Android Repository/Room → Compose` 流動。市場首頁由 `MarketOverviewService` 組合，不由 Router 直接拼接資料表；任一 section 缺資料時回傳 `PARTIAL`，不把缺值補成 0。

## Provider 與授權邊界

`TwseSecurityProvider` 與 `TpexSecurityProvider` 提供官方欄位至指數、融資融券及借券 Domain record 的 mapping 邊界；法人共用 mapper 保留 institution/dealer subtype。正式部署只允許 TWSE、TPEx 公開資料或另行簽約的合法來源，不解析非公開內部 API、不爬未授權網頁。`FakeMarketDataProvider` 是固定虛構 Fixture，包含 TAIEX、OTC、TWSE:1234、TPEX:5678，不是真實市場資料。

目前單日／backfill CLI 明確使用 Fake Provider，供驗收與本機重現；正式官方 endpoint 的逐資料集下載排程仍需依部署環境與官方欄位版本接線。上游沒有的值保存 `null`/`UNAVAILABLE`。

## Domain 與單位正規化

- 指數與百分比：`Decimal`；`change_percent` 是百分點。
- `turnover_amount`、市場法人 buy/sell/net：TWD `Decimal`，API 為 Decimal string。
- 個股法人 buy/sell/net：shares integer；不由股數推造金額。
- margin/short/lending 計數：Domain 統一 shares integer；若來源以張提供，由 Adapter 乘 1,000。
- `as_of`、`received_at`、`source_code`、`source_revision`、`data_status`、`ingestion_run_id` 保存於每筆資料。
- `net = buy - sell` 容許 TWD 0.01 的 Decimal rounding tolerance；官方 TOTAL 不被重新計算值覆蓋。

## Database 與 migration

Revision `0004_market_spot` 新增：`market_indexes`、`market_index_daily`、`market_breadth`、`market_institutional_spot`、`institution_spot_trading`、`market_margin_trading`、`margin_trading`、`market_securities_lending`、`securities_lending`。自然鍵以 market/security namespace、trade date、institution/dealer subtype 組成；查詢欄位均有 lookup index。

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic upgrade head
```

## Ingestion 與資料品質

每個 dataset 是獨立 transaction，因此單一 dataset 失敗不回滾同日其他資料。每次執行保存 ingestion run、checksum、insert/update/reject/retry；自然鍵 upsert 支援 revision update，第二次相同資料為 `inserted=0 updated=0`。驗證包含 OHLC、法人 net、非負 margin/lending/breadth 與同批重複資料。

```bash
make sync-market-spot DATE=2026-08-07
make backfill-market-spot FROM=2026-05-18 TO=2026-08-07
```

## API

- `GET /v1/market/overview`
- `GET /v1/market/indexes`
- `GET /v1/market/indexes/{indexCode}`
- `GET /v1/market/indexes/{indexCode}/candles`
- `GET /v1/market/breadth`
- `GET /v1/market/institutional/spot`
- `GET /v1/market/credit`
- `GET /v1/securities/{code}/institutional?market=TWSE`
- `GET /v1/securities/{code}/credit?market=TWSE`

法人與信用趨勢支援 1／5／10／20／60 個有效交易日，以及 `from`/`to`；週末不補 0。法人 response 包含 daily net、cumulative net 與連續方向日數，自營商保留 `PROPRIETARY`、`HEDGE`、`TOTAL`。Decimal 金額一律序列化為 string。

## Android

Bottom Navigation 為「市場／產業／持股／自選／更多」，本 Slice 只啟用市場。`feature-market` 具有 data/domain/presentation 邊界，市場首頁顯示資料狀態、TAIEX/OTC、廣度、法人期間與信用資料；漲跌以正負符號及文字輔助顏色。個股頁新增「籌碼」與「信用」Tab，不提供投資判斷。

UiState 明確區分 `Loading`、`Empty`、`Error`、`Offline`、`Partial`、`Success`；Room v3 保存 index、breadth、institutional、credit cache，key 包含 dataset/market/security/window/tradeDate。網路失敗時只顯示既存 cache 並標示 `STALE` 與 cache `as_of`，不冒充今日 FINAL。

## 測試與效能

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

Backend 測試涵蓋官方欄位 mapping、Fake、validation/idempotency、60 個交易日、dealer subtype、API/404/Decimal。Android 測試涵蓋 dashboard/partial/offline 與個股籌碼/信用；GitHub `android-instrumentation` 在 API 35 x86_64 執行 `connectedDebugAndroidTest`。

效能驗收以本機 Fake/PostgreSQL 執行 overview、60D institutional、security institutional/credit，並對主要 lookup query 執行 `EXPLAIN ANALYZE`；目標一般 API P95 < 500 ms、overview < 300 ms。最終數值與 CI run 於綠燈後補記。

2026-08-10 本機固定 Fixture 單次 smoke：overview 62.2 ms、market institutional 60D 15.8 ms、security institutional 60D 54.5 ms、security credit 14.7 ms；全部低於目標。PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)`：個股法人 360 rows 0.309 ms、個股融資 60 rows 0.108 ms。此為開發機單次量測，不宣稱正式流量 P95。

## 已知限制

- 只有盤後日資料，沒有即時、WebSocket 或分鐘資料。
- CLI 現階段使用 Fake fixture；正式排程需完成各官方公開 endpoint 的下載與欄位版本監控。
- Compose 第一版採輕量卡片/趨勢呈現，未引入額外 chart library。
- 不包含期貨、選擇權、PCR、VIX、產業強度、投資組合、自選股、篩選器、Alert 或 AI 摘要。

## CI 驗證紀錄

待本 Slice feature commit 推送且 GitHub Actions 實際綠燈後補入 run date、API 35、x86_64、測試數及 workflow run link；綠燈前不宣稱通過。
