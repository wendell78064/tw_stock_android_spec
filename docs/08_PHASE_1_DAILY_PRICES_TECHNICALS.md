# Phase 1／垂直切片 2 — 日 K、歷史價格與技術指標

## 範圍與架構

本切片建立 TWSE／TPEx 普通股日 K、日／週／月聚合、RAW／ADJUSTED 價格、可重現技術指標，以及 Android 個股走勢頁。資料流如下：

```text
Official/Fake Provider -> DailyPriceRecord (Decimal) -> validation
  -> daily_prices -> TechnicalIndicatorService -> technical_snapshots
  -> FastAPI/OpenAPI -> Android DTO -> Domain -> Room -> ViewModel/Canvas
```

分鐘與即時行情、法人、信用交易、借券、期貨、投資組合、自選股、Alert 及 AI 摘要均不在本切片。

## Provider 與授權邊界

- TWSE adapter 只呼叫交易所官方盤後每日收盤資料。
- TPEx adapter 只呼叫櫃買中心官方 OpenAPI 每日收盤資料。
- 官方欄位在 adapter 內轉成 `DailyPriceRecord`，不進入 API 或 Android。
- 正式來源不含可靠 adjusted OHLC 時保持 `null`；系統不猜測除權息係數。
- `PriceAdjustmentProvider` 是未來合法 adjusted source 的替換邊界。
- 測試及驗收使用虛構代號 `1234`／`5678` 的固定 Fake fixture，不依賴外網或當日行情。
- 上線前仍須複核官方資料保存、快取、呈現及重散布條款；不使用網頁爬蟲。

## Database 與 Migration

`0003_daily_prices_technicals` 建立：

- `daily_prices`：`(security_id, trade_date)` unique，NUMERIC OHLC/adjusted/turnover、股數、來源及 ingestion metadata。
- `technical_snapshots`：`(security_id, trade_date, price_basis)` unique，保存 RAW／ADJUSTED 各自的指標與 algorithm version。
- 日 K 查詢索引：`(security_id, trade_date DESC)` 及 `trade_date`。

```bash
make migrate
make migrate-down
make migrate
```

## Ingestion 與 Backfill

```bash
make sync-daily-prices DATE=2026-08-07
make backfill-security CODE=1234 MARKET=TWSE FROM=2025-01-01 TO=2026-08-07
make calculate-technicals CODE=1234 MARKET=TWSE
```

正式資料可將 CLI `--provider` 改為 `official`。同步先檢查 duplicate、OHLC 關係及負成交量；insert、官方 revision update 與 retry 都保存 ingestion run。單一不存在的 security 記為 rejected/partial，不讓其他股票回滾。

## RAW／ADJUSTED

- RAW：當日真實 OHLC，用於成交歷史呈現。
- ADJUSTED：只用於長期分析；Fake fixture 有固定 0.95 adjustment，正式來源缺值時 API 回 `UNAVAILABLE`。
- adjusted price 不宣稱是真實成交價格，Android 顯示「調整後技術分析價格」。
- RAW 與 ADJUSTED technical snapshots 分開計算與保存。

## K 線與 Range

`1d` 直接回日 K；`1w` 以 ISO week、`1mo` 以年月動態聚合。open/close 取首末交易日，high/low 取極值，volume/turnover 加總；休市日完全不補列。

- 1D：最近一個交易日日 K，明示不是分時。
- 5D／10D／30D／1Y：日 K。
- 5Y：Android 預設週 K，避免無限制圖表資料。

## 技術指標算法 v1

Algorithm version：`twml-technical-v1`。所有公式使用 Python `Decimal`，依已儲存交易日資料列計算。

- MA N：完整 N 筆 simple mean，否則 null。
- EMA N：前 N 筆 SMA seed；其後 `alpha=2/(N+1)`。
- RSI14：Wilder smoothing；首組 gain/loss 用 14 筆 simple mean。
- MACD：EMA12−EMA26；Signal 以首 9 筆 MACD SMA seed；Histogram=MACD−Signal。
- KD：9 日 RSV；K、D 初值 50，平滑 `(previous*2+current)/3`。
- ATR14：True Range 首 14 筆 SMA seed，後續 Wilder smoothing。
- OBV：第一筆 0，依 close 方向加減成交量；缺量回 null。
- Bollinger：20 日 population standard deviation，middle=MA20，upper/lower=`MA20 ± 2σ`。
- Williams %R：14 日 `(highest-close)/(highest-low)*-100`；區間為零時 null。

歷史 backfill 後會全量重算；日增量入口沿用同一 calculation service，確保初始化一致。

## API

```http
GET /v1/securities/{code}/candles?market=TWSE&range=1Y&interval=1d&adjustment=ADJUSTED
GET /v1/securities/{code}/technicals?market=TWSE&price_basis=ADJUSTED&indicators=MA20,RSI14,MACD
```

所有 Decimal 是 JSON string。回應包含 `as_of`、`received_at`、`data_status`、source、price basis 與 algorithm version。

## Android UI 與快取

個股頁分「走勢／基本資料」。走勢支援 range、RAW/ADJUSTED、主圖 overlay、副圖最多兩個、自訂 Compose Canvas K 線、pinch zoom、水平 pan、touch OHLCV inspection。Canvas 避免導入尚未驗證授權與 K 線互動能力的第三方 library。

Room candle cache key 包含 market、security、range、interval、adjustment；technical cache 包含 market、security、basis、date、indicator。離線快取固定標示 Offline/Stale，不當成最新資料。指標選擇以 DataStore 保存。

## 測試與驗證

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
```

Backend fixture 覆蓋 provider mapping、停牌/缺值、duplicate/partial、revision/idempotency/backfill、週/月聚合、全部指標、不足資料、API validation 與 Decimal。Android 覆蓋 remote/cache repository、K 線 rendering 與 OHLC selection。沒有 emulator 時只建置 instrumentation APK，`connectedDebugAndroidTest` 留給 CI emulator／實機。

## 已知限制

- 正式 adjusted OHLC 來源尚待授權與資料品質確認；不以 RAW 代替。
- TWSE/TPEx 官方 endpoint schema 修訂需同步更新 adapter fixture。
- `WeekendOnlyCalendar` 仍是 Phase 0 基礎實作；日 K 本身以官方實際資料列決定交易日，不產生休市資料。正式排程前仍需導入交易所行事曆 adapter。
- 圖表為 MVP Canvas renderer，尚未做分鐘線或硬體裝置效能基準。
