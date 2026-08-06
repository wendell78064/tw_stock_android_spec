# AGENTS.md — 台股 Android App AI 開發規則

## 1. 任務目標

建立可維護、可測試、可逐步上線的台股持股與市場籌碼 Android App。系統需整合台股現貨、台指期貨、三大法人、融資融券、借券、產業題材、投資組合、自選股、篩選器、比較與通知。

## 2. 每次開始工作前

依序閱讀：

1. `docs/00_MASTER_PRD.md`
2. `docs/01_APP_SCREEN_FLOW.md`
3. `docs/02_DATABASE_ERD.md`
4. `docs/03_BACKEND_API_SPEC.md`
5. `docs/04_DEVELOPMENT_ROADMAP.md`
6. `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
7. `api/openapi.yaml`

先確認目前 Phase 與尚未完成的驗收條件，再修改程式。

## 3. 開發原則

- 採用單一 Monorepo。
- Android 與 Backend 皆採 Feature／Domain 分層。
- API 以 `api/openapi.yaml` 為契約來源；修改 Endpoint 時同步更新 OpenAPI。
- Database schema 變更必須透過 Alembic migration，不直接修改正式資料庫。
- 上游 TWSE、TPEx、TAIFEX 或行情供應商皆透過 Adapter 介面，不讓官方欄位滲透到 Domain Model。
- 不以未授權網頁爬蟲提供正式盤中行情。
- 不在 UI 或 API 產生「買進、賣出、一定上漲」等投資建議，只呈現資料、規則命中與客觀狀態。
- 不自行捏造缺少的市場資料。資料缺失時回傳 `data_status`、`as_of` 與缺失原因。
- 所有金額與價格使用 Decimal，不使用浮點數直接計算損益。
- Database 時間以 UTC 儲存，API 使用 ISO 8601，Android 顯示為 `Asia/Taipei`。
- 交易日以台灣交易所行事曆判定，不以自然日計算均線。
- 股數統一以「股」儲存。5 張存為 `5000`，不得在資料庫以張為單位。
- 均線基準：MA5、MA10、MA20、MA60、MA120、MA240。
- 交易表單只允許：股票代號、BUY/SELL、日期時間、股數、價格、手續費、BOARD_LOT/ODD_LOT。
- 不新增公司事件或投資組合股利事件模組，除非使用者日後明確改變範圍。
- 賣出成本 MVP 採移動平均成本法。
- 稅額不是使用者輸入欄位。MVP 預設不納入損益；未來若加入自動稅額，必須使用可版本化規則且 UI 明確揭示。

## 4. Android 架構

建議模組：

```text
android-app/
├── app
├── core-model
├── core-network
├── core-database
├── core-ui
├── feature-market
├── feature-security
├── feature-industry
├── feature-portfolio
├── feature-watchlist
├── feature-screener
├── feature-alert
└── feature-settings
```

每個 Feature 至少包含：

- `data`
- `domain`
- `presentation`
- UI state
- ViewModel
- Repository interface
- Repository implementation
- Mapper
- Unit tests

Compose 規則：

- Screen 使用不可變 `UiState`。
- 使用單向資料流。
- Loading、Empty、Error、Stale、Success 狀態皆需處理。
- 顯示行情時必須呈現最後更新時間與資料狀態。
- 顏色不可作為唯一訊號；漲跌需同時使用符號或文字。
- 台股預設可使用紅漲綠跌，但需提供設定切換。

## 5. Backend 架構

建議結構：

```text
backend/
├── app/
│   ├── api
│   ├── core
│   ├── domain
│   ├── repositories
│   ├── services
│   ├── adapters
│   │   ├── twse
│   │   ├── tpex
│   │   ├── taifex
│   │   └── realtime_vendor
│   ├── jobs
│   └── main.py
├── migrations
└── tests
```

服務責任：

- `MarketDataService`：行情與指數。
- `InstitutionalService`：現貨與期貨法人。
- `CreditTradingService`：融資、融券、借券。
- `TechnicalIndicatorService`：MA、RSI、KD、MACD、ATR、OBV、布林通道。
- `IndustryService`：產業、題材、指標股及強度。
- `PortfolioService`：交易、部位、成本、損益。
- `AlertEngine`：規則計算、去重、冷卻與事件產生。
- `ScreenerService`：條件查詢。
- `NotificationService`：FCM 與通知紀錄。
- `IngestionService`：排程、重試、資料校驗及追補。

## 6. 測試要求

每一功能至少包含：

- Domain unit test。
- Repository／service test。
- API contract test。
- 重要資料轉換 fixture。
- Android ViewModel test。
- 至少一條 Compose UI happy-path test。

金融計算必測：

- 多次買進平均成本。
- 部分賣出。
- 全數賣出。
- 不可賣出超過持股。
- 零股與整股混合。
- 均線交易日計算。
- 盤中碰線、突破、跌破。
- 法人淨部位與日增減。
- 期現貨價差。
- API Decimal 精度。

## 7. 工作方式

每次只完成一個可驗收垂直切片：

1. 更新或確認契約。
2. Migration。
3. Backend Domain／Repository／API。
4. Android Repository／ViewModel／Screen。
5. 測試。
6. 文件。
7. 說明已完成與未完成項目。

不得一次生成大量無法執行的空殼檔案。若建立 TODO，需附上明確驗收條件。

## 8. Definition of Done

一項功能只有在以下條件全部成立時才算完成：

- 編譯成功。
- Migration 可正向與反向執行。
- OpenAPI 契約一致。
- 自動化測試通過。
- Loading、Empty、Error、Stale、Success UI 完成。
- API 回傳 `as_of`、`data_status`。
- 沒有 hard-coded 真實市場數值。
- README 或對應文件已更新。
