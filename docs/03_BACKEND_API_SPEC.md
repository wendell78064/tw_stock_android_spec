# 03 — Backend API Specification

## 1. API 原則

- Base URL：`/v1`
- JSON。
- ISO 8601 timestamp。
- Decimal 以 JSON string 傳輸，避免精度損失。
- 所有市場資料回傳 `as_of`、`received_at`、`data_status`。
- 使用 Bearer JWT。
- 分頁採 cursor。
- 寫入 API 支援 `Idempotency-Key`。
- API 不直接暴露上游交易所欄位名稱。

## 2. 共通回應

```json
{
  "data": {},
  "meta": {
    "as_of": "2026-08-06T05:30:00Z",
    "received_at": "2026-08-06T05:31:02Z",
    "data_status": "FINAL",
    "source": "TAIFEX"
  }
}
```

錯誤：

```json
{
  "error": {
    "code": "INSUFFICIENT_POSITION",
    "message": "賣出股數超過目前持股",
    "details": {
      "available_quantity": 500,
      "requested_quantity": 1000
    },
    "request_id": "..."
  }
}
```

## 3. Authentication

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /me`
- `PATCH /me/settings`
- `PUT /me/device-tokens/{token}`

## 4. 股票主檔與搜尋

### `GET /securities/search`

Query：

- `q`
- `market=TWSE|TPEX`
- `type=COMMON_STOCK`
- `limit`

回傳股票、產業與題材混合搜尋結果。

### `GET /securities/{code}`

回傳：

- 基本資料。
- 目前價格摘要。
- 所屬產業與題材。
- 最後更新狀態。

### `GET /securities/{code}/candles`

Query：

- `range=1D|5D|10D|30D|1Y|5Y`
- `interval=1m|5m|1d|1w|1mo`
- `adjustment=RAW|ADJUSTED`
- `from`
- `to`

### `GET /securities/{code}/technicals`

Query：

- `date`
- `indicators=MA,EMA,RSI,KD,MACD,ATR,OBV,BBANDS,WILLIAMS_R`
- `parameters`：JSON encoded 或改用 POST calculate。

### `GET /securities/{code}/institutional`

Query：

- `from`
- `to`
- `window=1|5|10|20|60`

### `GET /securities/{code}/credit`

回傳：

- 融資。
- 融券。
- 券資比。
- 借券。

### `GET /securities/{code}/signals`

回傳客觀規則命中，例如背離、突破、碰線。

## 5. 市場總覽

### `GET /market/overview`

一次取得首頁首屏：

- 加權與櫃買。
- 台指近月。
- 期現貨價差。
- 市場廣度。
- 三大法人現貨摘要。
- 三大法人期貨摘要。
- 融資融券借券摘要。
- Put／Call。
- VIX。
- 產業前五。

### `GET /market/indexes`

### `GET /market/indexes/{indexCode}`

### `GET /market/indexes/{indexCode}/candles`

### `GET /market/breadth`

Query：`market`、`date`。

### `GET /market/institutional/spot`

Query：`market`、`from`、`to`、`window`。

### `GET /market/credit`

Query：`market`、`from`、`to`。

### `GET /market/signals`

## 6. 期貨與選擇權

### `GET /futures/products`

### `GET /futures/products/{productCode}/overview`

回傳：

- 近月、次月。
- 日盤／夜盤。
- 期現貨價差。
- 成交量、未平倉。
- 到期資訊。

### `GET /futures/contracts/{contractCode}/candles`

### `GET /futures/products/{productCode}/continuous-candles`

Query：

- `range`
- `interval`
- `roll_method=VOLUME|OPEN_INTEREST|EXPIRY`

### `GET /futures/products/{productCode}/institutional-positions`

Query：

- `from`
- `to`
- `institution=FOREIGN|INVESTMENT_TRUST|DEALER|ALL`

### `GET /futures/products/{productCode}/open-interest`

### `GET /futures/products/{productCode}/trader-concentration`

Query：`top=5|10`、`side=LONG|SHORT|ALL`。

### `GET /options/products/{productCode}/put-call-ratio`

### `GET /options/products/{productCode}/open-interest-by-strike`

### `GET /options/products/{productCode}/max-pain`

需回傳：

- 計算日期。
- 使用到期月份。
- 演算法版本。
- 明確標示 `derived=true`。

### `GET /market/volatility`

## 7. 產業與題材

### `GET /industries`

Query：

- `type=OFFICIAL|THEME`
- `sort=strength|cap_return|equal_return|turnover|institutional|margin`
- `date`

### `GET /industries/{industryId}`

### `GET /industries/{industryId}/history`

### `GET /industries/{industryId}/securities`

Query：排序、分頁、篩選。

### `GET /industries/{industryId}/leaders`

### `GET /themes`

### `GET /themes/{themeId}`

管理端：

- `POST /admin/themes`
- `PATCH /admin/themes/{id}`
- `PUT /admin/themes/{id}/securities`
- `PUT /admin/industries/{id}/leaders`

## 8. 投資組合

### `GET /portfolios`

### `POST /portfolios`

```json
{
  "name": "主要持股"
}
```

### `GET /portfolios/{portfolioId}/summary`

回傳：

- 市值。
- 投入。
- 已實現／未實現。
- 今日損益。
- 個股與產業配置。
- 損益貢獻。
- `valuation_as_of`。

### `GET /portfolios/{portfolioId}/positions`

### `GET /portfolios/{portfolioId}/transactions`

### `POST /portfolios/{portfolioId}/transactions`

唯一允許的使用者交易欄位：

```json
{
  "stock_code": "2408",
  "transaction_type": "BUY",
  "transaction_time": "2026-08-06T09:15:00+08:00",
  "quantity_shares": 5000,
  "price": "470.00",
  "fee": "500.00",
  "lot_type": "BOARD_LOT"
}
```

### `PATCH /portfolios/{portfolioId}/transactions/{transactionId}`

欄位同新增。

### `DELETE /portfolios/{portfolioId}/transactions/{transactionId}`

刪除後重新計算受影響的部位。

### `GET /portfolios/{portfolioId}/performance`

Query：`from`、`to`、`interval=1d|1w|1mo`。

### `GET /portfolios/{portfolioId}/allocation`

Query：`group_by=security|industry|theme`。

## 9. 自選股

- `GET /watchlists`
- `POST /watchlists`
- `PATCH /watchlists/{id}`
- `DELETE /watchlists/{id}`
- `GET /watchlists/{id}/items`
- `POST /watchlists/{id}/items`
- `PATCH /watchlists/{id}/items/{itemId}`
- `DELETE /watchlists/{id}/items/{itemId}`
- `PUT /watchlists/{id}/items/reorder`
- `POST /watchlists/import`
- `GET /watchlists/{id}/export`

## 10. 提醒與通知

### Alert Rules

- `GET /alerts`
- `POST /alerts`
- `GET /alerts/{id}`
- `PATCH /alerts/{id}`
- `DELETE /alerts/{id}`
- `POST /alerts/{id}/enable`
- `POST /alerts/{id}/disable`
- `POST /alerts/preview`

規則類型至少包含：

- `PRICE_ABOVE`
- `PRICE_BELOW`
- `PRICE_NEAR_MA`
- `PRICE_CROSS_MA_UP`
- `PRICE_CROSS_MA_DOWN`
- `CLOSE_ABOVE_MA`
- `CLOSE_BELOW_MA`
- `VOLUME_ABOVE_AVERAGE`
- `INSTITUTION_CONSECUTIVE_BUY`
- `INSTITUTION_NET_THRESHOLD`
- `MARGIN_CHANGE_THRESHOLD`
- `LENDING_CHANGE_THRESHOLD`
- `FOREIGN_FUTURES_NET_OI_CHANGE`
- `FUTURES_BASIS_THRESHOLD`
- `PUT_CALL_THRESHOLD`
- `VIX_THRESHOLD`
- `INDUSTRY_STRENGTH_THRESHOLD`
- `SAVED_SCREENER_MATCH`

### Notifications

- `GET /notifications`
- `PATCH /notifications/{id}/read`
- `POST /notifications/read-all`
- `DELETE /notifications/{id}`
- `GET /notification-settings`
- `PATCH /notification-settings`

## 11. 篩選器

### `POST /screeners/run`

```json
{
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "field": "price.distance_to_ma20_percent",
        "operator": "LTE",
        "value": 1.0
      },
      {
        "field": "institution.foreign.net_5d",
        "operator": "GT",
        "value": 0
      }
    ]
  },
  "sort": [
    {
      "field": "industry.strength_score",
      "direction": "DESC"
    }
  ],
  "limit": 100
}
```

- `GET /screeners/saved`
- `POST /screeners/saved`
- `PATCH /screeners/saved/{id}`
- `DELETE /screeners/saved/{id}`

## 12. 個股比較

### `POST /comparisons`

```json
{
  "stock_codes": ["2408", "2344", "2337"],
  "range": "1Y",
  "metrics": [
    "NORMALIZED_RETURN",
    "FOREIGN_NET",
    "MARGIN_CHANGE",
    "RSI14",
    "DISTANCE_TO_MA20"
  ]
}
```

最多 5 檔。

## 13. 報表、同步及 AI 摘要

- `POST /reports/portfolio`
- `GET /reports/{id}`
- `POST /sync/export`
- `POST /sync/import`
- `POST /summaries/market`
- `POST /summaries/portfolio/{portfolioId}`

AI 摘要回傳：

- 摘要文字。
- 使用資料日期。
- 引用指標清單。
- 規則命中。
- 資料缺失。
- 免責聲明。

## 14. WebSocket

Endpoint：

`GET /ws/market?token=...`

Client message：

```json
{
  "action": "subscribe",
  "channels": [
    "index:TAIEX",
    "future:TX_NEAR",
    "security:2408",
    "portfolio:default"
  ]
}
```

Server event：

```json
{
  "type": "quote.updated",
  "channel": "security:2408",
  "sequence": 123456,
  "as_of": "2026-08-06T01:20:05Z",
  "data_status": "LIVE",
  "payload": {
    "last": "485.00",
    "change_percent": "1.46",
    "volume_shares": 12345000
  }
}
```

其他事件：

- `index.updated`
- `future.updated`
- `breadth.updated`
- `portfolio.valuation.updated`
- `alert.triggered`
- `data_status.changed`

要求：

- sequence 可偵測漏訊息。
- 重連後支援 REST snapshot 再續訂。
- heartbeat。
- 每位使用者訂閱上限。
- 不透過 WebSocket 傳送完整歷史 K 線。

## 15. 快取建議

- 市場首頁：Redis 5–15 秒盤中；盤後 5 分鐘。
- 股票主檔：24 小時。
- 日 K：盤後更新後長快取。
- 技術指標：每日計算後長快取。
- 使用者持股：寫入後主動失效。
- 產業快照：盤中 15–60 秒；盤後固定版本。

## 16. Rate Limits

- Anonymous search：30/min/IP。
- Authenticated read：300/min/user。
- Transaction write：60/min/user。
- Screener：20/min/user。
- AI summary：依方案限制。
- WebSocket subscription：依使用者與授權限制。
