# Phase 1／垂直切片 1 — 股票主檔與搜尋

## 範圍

本切片只處理 TWSE 上市普通股與 TPEx 上櫃普通股的主檔、同步、搜尋及 Android 基本資料頁。ETF、ETN、權證、特別股、TDR、興櫃、債券、衍生品及 inactive 商品不進入預設搜尋。沒有股價、日 K、技術指標、法人、信用交易、投資組合、自選股或即時行情。

## 股票主檔來源與授權

- TWSE Adapter：交易所官方 OpenAPI `t187ap03_L`。
- TPEx Adapter：櫃買中心官方 OpenAPI `mopsfin_t187ap03_O`。
- 上游欄位只存在於 `backend/app/adapters/twse` 與 `backend/app/adapters/tpex`；進入系統前轉成 `SecurityRecord`。
- 正式同步只存主檔公開資訊，不使用網頁爬蟲，也不取得或散布盤中行情。
- 官方 endpoint 與欄位可能修訂，上線前仍需複核官方使用條款及 Adapter mapping。

驗收與自動化測試使用 `FakeMarketDataProvider` 的固定合成資料，不依賴外網或當日市場內容。

## 資料表

- `markets`：市場 namespace；股票不能只用代號識別。
- `securities`：普通股主檔與 `source_code/as_of/received_at/data_status`。
- `industries`：依分類來源及代碼唯一。
- `security_industries`：主要產業關聯。
- `ingestion_runs`：同步狀態、筆數、checksum 與錯誤。

唯一鍵為 `securities(market_id, code)`。名稱使用 PostgreSQL trigram index；inactive 商品保留於資料庫但不顯示於搜尋。

## 同步

先啟動服務，再執行固定 Fixture：

```bash
make up
make sync-securities
```

同一指令重跑應顯示 `inserted=0 updated=0`。正式官方來源需明確執行：

```bash
docker compose exec backend python -m app.cli.sync_securities --provider official
```

正式命令會連線官方 OpenAPI，應由具備資料使用授權及網路政策的部署環境執行。同步依市場分開校驗；新增會 insert、變更會 update、來源清單消失的商品會標成 inactive，不直接刪除。

## API

```http
GET /v1/securities/search?q={query}&market=TWSE|TPEX&type=COMMON_STOCK&limit=20
GET /v1/securities/{code}?market=TWSE|TPEX
```

搜尋至少輸入 2 個字元，支援完整代號、代號前綴、完整／部分中文名稱與市場篩選。若相同代號跨市場且 detail 未帶 `market`，回傳 `409 AMBIGUOUS_SECURITY`；不存在回傳 `404 SECURITY_NOT_FOUND`。所有結果包含 UTC 資料時間與資料狀態。

## Android 操作與架構

首頁 Top App Bar 點選「搜尋」，輸入至少 2 個字元；350 ms debounce 後呼叫搜尋 API，也可用鍵盤搜尋。點擊結果進入個股基本資料頁。

資料流：

```text
OpenAPI contract / Retrofit DTO
  -> feature-security Mapper
  -> Security Domain Model
  -> Repository / Use Case / ViewModel
  -> immutable Compose UiState
```

Room `security_cache` 保存最近成功的主檔結果；網路失敗且有快取時顯示 Stale，無快取時顯示 Offline。搜尋畫面明確處理 Idle、Loading、Empty、Error、Offline、Stale、Success。個股頁只顯示主檔，並明示後續行情功能尚未提供。

## 測試與建置

```bash
make backend-lint
make backend-test
make backend-build
make openapi-validate
make openapi-generate
make android-lint
make android-test
make android-build
make android-ui-test-apk
make migrate-down
make migrate-up
```

Backend 覆蓋 Provider mapping、Fake metadata、insert/update/idempotency、跨市場、重複、inactive、搜尋與 404/409。Android 覆蓋 DTO/enum/Decimal mapping、Repository/cache、debounce、ViewModel 狀態及兩條 Compose UI happy path。

## 已知限制

- 第一版以官方公司主檔及普通股代碼規則過濾；官方分類規則修訂時需更新 Adapter fixture。
- 產業名稱缺失時保持 `null`，不自行補造。
- 最近搜尋只保留 UI 擴充位置，本切片不保存歷史。
- Compose UI 測試 APK 已編譯；完整裝置互動仍需 CI emulator 或實機執行 instrumentation test。
- 日 K 與技術指標屬下一垂直切片，目前未實作。
