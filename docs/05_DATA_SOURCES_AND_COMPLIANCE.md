# 05 — Data Sources and Compliance

> 本文件列出資料整合方向，不代表自動取得即時行情的授權。公開上架前需由產品／法務再次確認使用條款。

## 1. 官方公開資料來源

### TWSE 臺灣證券交易所

用途：

- 上市股票主檔。
- 上市每日行情。
- 集中市場三大法人。
- 上市個股法人。
- 集中市場及個股融資融券。
- 借券相關盤後資料。
- 指數與市場統計。

官方入口：

- `https://openapi.twse.com.tw/`
- `https://www.twse.com.tw/`

### TPEx 證券櫃檯買賣中心

用途：

- 上櫃股票主檔。
- 上櫃每日行情。
- 上櫃三大法人。
- 上櫃融資融券。
- 借券與市場統計。
- 櫃買指數。

官方入口：

- `https://www.tpex.org.tw/openapi/`
- `https://www.tpex.org.tw/`

### TAIFEX 臺灣期貨交易所

用途：

- 期貨每日交易行情。
- 台指期未平倉。
- 三大法人期貨及選擇權部位。
- 各期貨契約法人部位。
- Put／Call Ratio。
- 前五大／前十大交易人未平倉。
- 選擇權未平倉。
- 臺指選擇權波動率指數。

官方入口：

- `https://openapi.taifex.com.tw/`
- `https://www.taifex.com.tw/`

## 2. 盤中即時行情

正式產品不可假設官方盤後 OpenAPI 等同即時行情授權。

設計要求：

- `RealtimeMarketDataProvider` 抽象介面。
- 可替換供應商。
- Provider 回傳授權等級：LIVE／DELAYED／EOD。
- UI 明確顯示延遲。
- 不將供應商原始欄位直接寫入 Domain。
- 不超出授權範圍快取、保存或重散布。
- WebSocket 使用者數與商品訂閱數需受授權限制。

## 3. Ingestion Adapter

```python
class MarketDataProvider(Protocol):
    async def list_securities(self) -> list[SecurityRecord]: ...
    async def get_daily_prices(self, trade_date: date) -> list[DailyPriceRecord]: ...
    async def get_market_institutional(self, trade_date: date) -> list[InstitutionRecord]: ...
    async def get_security_institutional(self, trade_date: date) -> list[InstitutionRecord]: ...
    async def get_margin_trading(self, trade_date: date) -> list[MarginRecord]: ...
    async def get_lending(self, trade_date: date) -> list[LendingRecord]: ...
```

```python
class DerivativesDataProvider(Protocol):
    async def get_futures_daily(self, trade_date: date) -> list[FuturesDailyRecord]: ...
    async def get_institution_positions(self, trade_date: date) -> list[InstitutionFuturesRecord]: ...
    async def get_trader_concentration(self, trade_date: date) -> list[ConcentrationRecord]: ...
    async def get_put_call_ratio(self, trade_date: date) -> PutCallRecord: ...
    async def get_volatility_index(self, trade_date: date) -> VolatilityRecord: ...
```

## 4. 更新時序

實際公布時間需由 Job 以「資料可用性」判斷，不只依固定時間。

### 盤中

- 即時／延遲個股及指數。
- 期貨日盤與夜盤。
- 市場廣度。
- 分鐘 K 線。
- 盤中均線碰觸。
- 期現貨價差。

### 盤後

依序：

1. 現貨收盤行情。
2. 市場廣度。
3. 法人現貨。
4. 融資融券。
5. 借券。
6. 期貨每日行情與未平倉。
7. 三大法人期貨部位。
8. Put／Call、集中度與 VIX。
9. 技術指標。
10. 產業快照。
11. 投資組合估值。
12. Alert Engine。
13. 通知推送。

## 5. Job 狀態

`ingestion_runs`：

- provider。
- dataset。
- trade_date。
- started_at。
- finished_at。
- status。
- fetched_count。
- inserted_count。
- updated_count。
- rejected_count。
- checksum。
- error_message。
- retry_count。

狀態：

- PENDING。
- RUNNING。
- SUCCEEDED。
- PARTIAL。
- FAILED。
- SKIPPED。

## 6. 校驗

每個 dataset 至少檢查：

- 日期格式。
- 重複 key。
- 負值不合理欄位。
- 買賣超是否等於買進減賣出。
- 期貨淨部位是否等於多方減空方。
- OHLC 合理性。
- 股票代號是否存在。
- 當日筆數與近期中位數差異。
- 官方修訂資料能覆蓋舊版。
- 上市／上櫃同代號 namespace。

## 7. 連續月期貨

連續月不是官方單一真實契約，需保存演算法：

- `VOLUME`：成交量較大時轉倉。
- `OPEN_INTEREST`：未平倉較大時轉倉。
- `EXPIRY`：到期前固定交易日轉倉。

API 必須回傳：

- roll method。
- 本次使用契約。
- roll date。
- 是否做價差調整。
- algorithm version。

## 8. 還原權息價格

雖然不建立持股事件輸入，長期圖表仍可由資料供應來源提供 adjusted price，或由行情處理層計算。

規則：

- RAW 與 ADJUSTED 分開儲存。
- 技術指標的 price basis 必須記錄。
- UI 清楚顯示目前模式。
- 不可用調整後價格當作真實成交價格。

## 9. 法人資料解讀限制

三大法人類別是多家機構的合計結果，不代表單一法人或整體機構使用同一策略。產品只能陳述：

- 買賣超。
- 未平倉多空淨額。
- 日變化。
- 歷史關聯與規則命中。

不可宣稱能由單一數值確定未來方向。

## 10. 資料保留

建議：

- 日 K：長期保存。
- 分鐘 K：依授權與成本設定。
- Tick：MVP 不保存。
- 首頁快照：保存每日收盤版。
- Alert observed values：保存供使用者追溯。
- 上游 raw payload：短期保存，並移除不允許保存的資料。

## 11. 上線前檢查

- TWSE、TPEx、TAIFEX 使用條款。
- 即時行情供應契約。
- App 內資料來源揭示。
- 延遲時間標示。
- 使用者條款。
- 隱私政策。
- 投資風險免責聲明。
- FCM 與分析服務的隱私揭露。
