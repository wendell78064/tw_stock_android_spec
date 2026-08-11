# Phase 3 / Slice 1：Portfolio Core

本 Slice 建立 Portfolio、交易帳本、移動平均成本、持股估值與 Android 持股首頁。交易帳本是唯一 accounting source of truth；本 Slice 不建立 position ledger、每日 snapshot 或公司事件。

## Architecture

Backend 由 `PortfolioRepository` 保存 portfolio 與 transaction，`PortfolioAccountingService` 以單次 replay 計算 position，`PortfolioService` 結合 Security master 與 Phase 1 DailyPrice 產生 holdings／summary。Android 經既有 Retrofit、Repository、ViewModel、Compose 與 Room 讀取；Room 只作離線唯讀 cache。

## Transaction Model

輸入欄位只有股票代號、市場、`BUY`／`SELL`、成交時間、股數、價格、手續費及 `ROUND_LOT`／`ODD_LOT`。Domain 與 DB 永遠以 `quantity_shares` 保存股數；5 張必須保存為 5000 shares。交易依 `executed_at ASC, created_at ASC, id ASC` deterministic replay。

建立與刪除交易均重新驗證完整 ledger。刪除歷史交易後若後續交易造成超賣，操作會被拒絕；position 不會成為負數。

## Moving Average Cost

BUY：

```text
buy_cost = quantity_shares × price + fee
new_quantity = old_quantity + buy_quantity
new_cost_basis = old_cost_basis + buy_cost
new_average_cost = new_cost_basis / new_quantity
```

SELL：

```text
average_cost = current_cost_basis / current_quantity
sold_cost_basis = sell_quantity × average_cost
realized_pnl = sell_quantity × sell_price - fee - sold_cost_basis
new_quantity = old_quantity - sell_quantity
new_cost_basis = old_cost_basis - sold_cost_basis
```

全數賣出時 `new_cost_basis=0`、`average_cost=null`。SELL 不改變剩餘持股平均成本。`SELL > available shares` 回傳 `PORTFOLIO_INSUFFICIENT_POSITION`。

## Financial Precision and Tax

Backend 使用 Python `Decimal`、PostgreSQL `NUMERIC(24,8)`，API 金額輸出 Decimal string；Android 不以 binary float 計算金融金額。MVP 損益為 `tax_handling=NOT_INCLUDED`：使用者不輸入交易稅，也不 hard-code 未版本化稅率。

## Database

Alembic `0006_portfolio_core` 建立：

- `portfolios`
- `portfolio_transactions`
- `(portfolio_id, executed_at)` index
- `(portfolio_id, security_id, executed_at)` index
- Default Portfolio

Positions、summary 與 allocation 採 request-time single-pass calculation。未建立 transaction ledger 以外的 accounting source。

## Price Source and P&L

估值沿用 Phase 1 latest available daily close：

```text
market_value = quantity_shares × latest_price
unrealized_pnl = market_value - remaining_cost_basis
unrealized_return_percent = unrealized_pnl / remaining_cost_basis × 100
allocation_percent = holding_market_value / total_market_value × 100
```

缺少行情時 `latest_price`、`market_value`、`unrealized_pnl` 保持 `null`，不補 0。不同估值日期或部分缺漏使 summary 為 `PARTIAL`；上游 stale 使 summary 為 `STALE`。

## API

- `GET /v1/portfolios`
- `POST /v1/portfolios`
- `GET /v1/portfolios/{portfolioId}`
- `GET /v1/portfolios/{portfolioId}/transactions`
- `POST /v1/portfolios/{portfolioId}/transactions`
- `DELETE /v1/portfolios/{portfolioId}/transactions/{transactionId}`
- `GET /v1/portfolios/{portfolioId}/positions`
- `GET /v1/portfolios/{portfolioId}/summary`

## Android

`feature-portfolio` 啟用 bottom navigation 的「持股」入口，提供總市值、總成本、已／未實現損益、報酬率、價格狀態、security allocation、holding sorting、交易表單、holding detail、交易紀錄與刪除確認。個股圖表沿用 Security Detail，不複製 K-line。

## Offline

API 成功後更新 Room summary／holding／transaction cache。離線時可讀最後 cache 並標記 Offline／Stale；新增與刪除必須連線成功，本 Slice 不建立 offline write queue、conflict resolution 或 cloud sync。

## Tests

Backend 測試涵蓋 first／multiple BUY、fee、average cost、partial／full SELL、oversell、multiple securities、same timestamp、delete replay、Decimal、daily close、missing／stale price、unknown／ambiguous security、summary、allocation、empty、API contract 與 1000 筆 replay smoke。

Android 測試涵蓋 repository cache、ViewModel states、sorting、transaction validation、dashboard、empty、holding row、add transaction、BUY／SELL、holding detail 與 transaction delete confirmation。Instrumentation 使用固定 fixture，不依賴正式 TWSE 網路。

## Known Limitations

- 不含交易稅與版本化稅規則
- 不含 dividend／ex-right／ex-dividend／capital events
- 不含 realtime／minute K／WebSocket
- 不含 offline write queue／cloud sync／broker integration
- 不含 industry allocation、watchlist、alerts、screener 或 AI summary
