# 04 — Development Roadmap

## Phase 0：專案基礎

### 任務

- 建立 Monorepo。
- Android Compose 專案。
- FastAPI 專案。
- PostgreSQL、Redis、Docker Compose。
- OpenAPI code generation。
- CI：lint、test、build。
- logging、settings、health check。
- 建立 Adapter interface 與 fake data provider。
- 建立交易日 calendar abstraction。

### 驗收

- 一行命令啟動 Backend、DB、Redis。
- Android Debug 可連本機 API。
- `/health`、`/ready` 正常。
- CI 可編譯 Android 並執行 Backend tests。
- 不含任何 hard-coded 真實行情。

## Phase 1：盤後 MVP

### 垂直切片 1：股票主檔與搜尋

狀態：**已完成並通過 build、test、migration、同步及 API 驗證。**

- TWSE／TPEx 主檔 Adapter。
- `securities`、industry tables。
- 搜尋 API。
- Android 搜尋及個股基本頁。

驗收：

- 代號、名稱模糊搜尋。
- 僅顯示上市／上櫃普通股。
- 明確顯示資料日期。

實作與操作紀錄：`docs/07_PHASE_1_SECURITY_MASTER.md`。本次完成範圍不包含下方垂直切片 2。

### 垂直切片 2：日 K 與技術指標

狀態：**已完成實作；驗證與操作紀錄見 `docs/08_PHASE_1_DAILY_PRICES_TECHNICALS.md`。**

- 日行情 ingestion。
- 1M／1Y／5Y 日、週、月聚合。
- MA、RSI、KD、MACD、ATR、OBV、BBands。
- K 線頁。

驗收：

- MA 使用交易日。
- 調整／未調整切換。
- 上游缺資料時不補假數值。

### 垂直切片 3：自選股

- 多群組 CRUD。
- 排序。
- 目標、停損、加碼價。
- Room 離線快取。

### 垂直切片 4：投資組合

- 交易 CRUD。
- 移動平均成本。
- Position rebuild。
- 持股及損益頁。

驗收案例：

- 多次買進。
- 部分賣出。
- 全數賣出。
- 零股與整股混合。
- 拒絕超賣。
- 編輯歷史交易後重算。

### 垂直切片 5：收盤均線提醒

- Alert Rule CRUD。
- 盤後評估。
- 通知中心。
- FCM。

## Phase 2：市場、法人、信用與期貨盤後資料

### 任務

- 加權、櫃買市場首頁。
- 市場廣度。
- 三大法人現貨。
- 融資、融券、借券。
- 台指期每日行情與未平倉。
- 三大法人期貨未平倉。
- 期現貨價差。
- Put／Call、VIX。
- 前五大／前十大未平倉。
- 大盤多空儀表板。
- 背離規則。
- 個股籌碼與信用 Tab。

### 驗收

- 現貨與期貨資料日期一致性檢查。
- 期貨多、空、淨額計算通過。
- 自營商自行買賣／避險正確拆分。
- 法人資料可查 1／5／10／20／60 日。
- 每個 API 顯示來源與狀態。

## Phase 3：產業、題材、篩選器與比較

### 任務

- 官方產業與自訂題材。
- 指標股管理。
- 等權、市值加權、強度分數。
- 產業法人、信用與廣度。
- 股票篩選器。
- 儲存篩選器及通知。
- 2–5 檔比較。
- 背離與客觀訊號。

### 驗收

- 同一股票可屬多題材。
- 市值加權分母可追溯。
- 強度分數版本化。
- 篩選器 AND／OR 結果可重現。
- 比較圖起點正規化一致。

## Phase 4：合法盤中行情

### 前置條件

- 已確認即時或延遲行情授權。
- 已完成供應商 Adapter。
- 已確認使用者數、重散布與快取權限。

### 任務

- WebSocket ingestion。
- Redis quote cache。
- Android WebSocket。
- 1m／5m K 線。
- 盤中碰線。
- 即時期現貨價差。
- 夜盤。
- 盤中產業強度。
- Push 去重與冷卻。

### 驗收

- 重連。
- sequence gap recovery。
- 快照＋增量一致。
- stale detection。
- 盤中同規則不重複轟炸。
- App 背景恢復後資料正確。

## Phase 5：完整產品功能

- 多裝置同步。
- 生物辨識。
- 桌面小工具。
- CSV 匯入／匯出。
- PDF／CSV 報表。
- 模擬投資組合。
- 離線模式。
- 最大痛點估算。
- AI 市場與持股摘要。
- 訂閱與額度管理。
- 管理後台。
- Data quality dashboard。

## 建議第一個 Codex 任務

```text
請先閱讀根目錄 AGENTS.md 與 docs/00～05。只執行 Phase 0，不實作市場功能。
建立 Monorepo：android-app 使用 Kotlin、Jetpack Compose、Hilt；backend 使用 FastAPI、SQLAlchemy 2、Alembic；infra 使用 Docker Compose 啟動 PostgreSQL 與 Redis。
建立 /health、/ready、統一錯誤格式、設定管理、結構化日誌及最小 CI。建立 MarketDataProvider 介面與 FakeMarketDataProvider，禁止直接爬取網站。
完成後執行測試與 build，列出建立檔案、執行指令、測試結果及下一個垂直切片，不要開始 Phase 1。
```

## 後續 Codex 任務模板

```text
請閱讀 AGENTS.md、相關 docs 與 api/openapi.yaml。
目前只完成「{垂直切片名稱}」。

先列出：
1. 需求與驗收條件。
2. 會修改的模組。
3. Database migration。
4. API 契約變更。
5. Android UI state。
6. 測試案例。

接著完成可執行的 Backend、Android、migration、測試與文件。使用 Fake Provider 讓測試可重現。
不得開始下一個切片，不得使用未授權網頁爬蟲，不得捏造真實行情。
最後提供 build/test 結果與尚未完成項目。
```
# Phase 1 / Slice 2 Hardening

- 技術指標數值參數編輯、驗證、保存與重設：完成
- 預設 snapshot／自訂 request-time calculation：完成
- Android emulator instrumentation workflow：完成建置，執行結果以 CI run 為準

# Phase 2 / Slice 1：市場現貨、法人與信用交易

- market index／breadth、三大法人現貨、融資融券與借券 Domain/DB/API：完成
- deterministic Fake ingestion、冪等與 60 交易日趨勢：完成
- Android 市場首頁、個股籌碼/信用 Tab、Room offline cache：完成
- API 35 x86_64 instrumentation：feature commit 推送後以實際 GitHub Actions 結果封版
