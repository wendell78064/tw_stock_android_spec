# 02 — Database ERD

## 1. 設計原則

- PostgreSQL 為主資料庫。
- 日線資料可先使用原生分區表；分鐘資料量上升後啟用 TimescaleDB。
- 所有價格、金額使用 `NUMERIC`。
- 所有交易數量以「股」儲存。
- 所有時間以 UTC 儲存。
- `trade_date` 使用台灣交易日期。
- 上游原始資料可保存於 staging schema，Domain 表使用統一欄位。
- 不建立投資組合公司事件／股利事件表。

## 2. 市場主檔 ERD

```mermaid
erDiagram
    MARKETS ||--o{ SECURITIES : contains
    INDUSTRIES ||--o{ SECURITY_INDUSTRIES : classifies
    SECURITIES ||--o{ SECURITY_INDUSTRIES : belongs
    THEMES ||--o{ SECURITY_THEMES : tags
    SECURITIES ||--o{ SECURITY_THEMES : belongs
    SECURITIES ||--o{ DAILY_PRICES : has
    SECURITIES ||--o{ INTRADAY_BARS : has
    SECURITIES ||--o{ TECHNICAL_SNAPSHOTS : has
    INDUSTRIES ||--o{ INDUSTRY_SNAPSHOTS : has
    SECURITIES ||--o{ INDUSTRY_LEADERS : selected
    INDUSTRIES ||--o{ INDUSTRY_LEADERS : defines

    MARKETS {
      uuid id PK
      varchar code UK
      varchar name
      varchar timezone
    }

    SECURITIES {
      uuid id PK
      uuid market_id FK
      varchar code
      varchar name
      varchar security_type
      boolean is_active
      date listing_date
      date delisting_date
      bigint shares_outstanding
    }

    INDUSTRIES {
      uuid id PK
      varchar code UK
      varchar name
      varchar classification_source
    }

    THEMES {
      uuid id PK
      varchar slug UK
      varchar name
      text description
    }

    SECURITY_INDUSTRIES {
      uuid security_id FK
      uuid industry_id FK
      boolean is_primary
    }

    SECURITY_THEMES {
      uuid security_id FK
      uuid theme_id FK
      numeric relevance_weight
    }

    DAILY_PRICES {
      uuid security_id FK
      date trade_date
      numeric open
      numeric high
      numeric low
      numeric close
      numeric adjusted_close
      bigint volume_shares
      numeric turnover_amount
    }

    INTRADAY_BARS {
      uuid security_id FK
      timestamptz bar_time
      smallint interval_minutes
      numeric open
      numeric high
      numeric low
      numeric close
      bigint volume_shares
    }

    TECHNICAL_SNAPSHOTS {
      uuid security_id FK
      date trade_date
      numeric ma5
      numeric ma10
      numeric ma20
      numeric ma60
      numeric ma120
      numeric ma240
      numeric rsi14
      numeric macd
      numeric macd_signal
      numeric kd_k
      numeric kd_d
      numeric atr14
      numeric obv
    }

    INDUSTRY_SNAPSHOTS {
      uuid industry_id FK
      timestamptz observed_at
      numeric equal_weight_return
      numeric cap_weight_return
      numeric turnover_amount
      numeric market_turnover_share
      integer advancers
      integer decliners
      numeric above_ma20_ratio
      numeric above_ma60_ratio
      numeric strength_score
    }

    INDUSTRY_LEADERS {
      uuid industry_id FK
      uuid security_id FK
      smallint rank
      text rationale
    }
```

## 3. 指數、期貨、法人與信用交易 ERD

```mermaid
erDiagram
    MARKET_INDEXES ||--o{ INDEX_BARS : has
    FUTURES_PRODUCTS ||--o{ FUTURES_CONTRACTS : contains
    FUTURES_CONTRACTS ||--o{ FUTURES_BARS : has
    FUTURES_CONTRACTS ||--o{ FUTURES_OPEN_INTEREST : has
    FUTURES_PRODUCTS ||--o{ INSTITUTION_FUTURES_POSITIONS : has
    SECURITIES ||--o{ INSTITUTION_SPOT_TRADING : has
    SECURITIES ||--o{ MARGIN_TRADING : has
    SECURITIES ||--o{ SECURITIES_LENDING : has

    MARKET_INDEXES {
      uuid id PK
      varchar code UK
      varchar name
      varchar market
    }

    INDEX_BARS {
      uuid index_id FK
      timestamptz observed_at
      varchar timeframe
      numeric open
      numeric high
      numeric low
      numeric close
      numeric turnover_amount
    }

    FUTURES_PRODUCTS {
      uuid id PK
      varchar code UK
      varchar name
      varchar session_type
      numeric contract_multiplier
    }

    FUTURES_CONTRACTS {
      uuid id PK
      uuid product_id FK
      varchar contract_code UK
      date expiry_date
      boolean is_near_month
      boolean is_next_month
    }

    FUTURES_BARS {
      uuid contract_id FK
      timestamptz observed_at
      varchar timeframe
      numeric open
      numeric high
      numeric low
      numeric close
      bigint volume
    }

    FUTURES_OPEN_INTEREST {
      uuid contract_id FK
      date trade_date
      bigint open_interest
      bigint open_interest_change
      numeric settlement_price
    }

    INSTITUTION_SPOT_TRADING {
      uuid security_id FK
      date trade_date
      varchar institution_type
      varchar dealer_subtype
      numeric buy_amount
      numeric sell_amount
      numeric net_amount
    }

    MARKET_INSTITUTION_SPOT {
      varchar market_code
      date trade_date
      varchar institution_type
      varchar dealer_subtype
      numeric buy_amount
      numeric sell_amount
      numeric net_amount
    }

    MARGIN_TRADING {
      uuid security_id FK
      date trade_date
      bigint margin_buy
      bigint margin_sell
      bigint margin_cash_repayment
      bigint margin_balance
      bigint short_sell
      bigint short_cover
      bigint short_stock_repayment
      bigint short_balance
      numeric margin_utilization
      numeric short_utilization
      numeric short_margin_ratio
    }

    MARKET_MARGIN_TRADING {
      varchar market_code
      date trade_date
      bigint margin_balance
      bigint margin_change
      bigint short_balance
      bigint short_change
      numeric short_margin_ratio
    }

    SECURITIES_LENDING {
      uuid security_id FK
      date trade_date
      bigint lending_sell
      bigint lending_return
      bigint lending_balance
      bigint lending_balance_change
    }

    MARKET_SECURITIES_LENDING {
      varchar market_code
      date trade_date
      bigint lending_sell
      bigint lending_return
      bigint lending_balance
      bigint lending_balance_change
    }

    INSTITUTION_FUTURES_POSITIONS {
      uuid product_id FK
      date trade_date
      varchar institution_type
      bigint long_oi
      bigint short_oi
      bigint net_oi
      numeric long_amount
      numeric short_amount
      numeric net_amount
      bigint long_oi_change
      bigint short_oi_change
      bigint net_oi_change
    }

    TRADER_CONCENTRATION {
      uuid product_id FK
      date trade_date
      varchar side
      smallint top_n
      bigint open_interest
      numeric concentration_ratio
    }

    OPTION_MARKET_STATS {
      date trade_date
      varchar product_code
      numeric volume_put_call_ratio
      numeric oi_put_call_ratio
      numeric volatility_index
      numeric max_pain
      numeric max_call_oi_strike
      numeric max_put_oi_strike
    }
```

## 4. 使用者、投資組合、自選與提醒 ERD

```mermaid
erDiagram
    USERS ||--o{ PORTFOLIOS : owns
    PORTFOLIOS ||--o{ TRANSACTIONS : records
    PORTFOLIOS ||--o{ POSITIONS : contains
    PORTFOLIOS ||--o{ POSITION_SNAPSHOTS : snapshots
    USERS ||--o{ WATCHLISTS : owns
    WATCHLISTS ||--o{ WATCHLIST_ITEMS : contains
    SECURITIES ||--o{ WATCHLIST_ITEMS : tracks
    USERS ||--o{ ALERT_RULES : owns
    ALERT_RULES ||--o{ ALERT_EVENTS : triggers
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ SAVED_SCREENERS : owns

    USERS {
      uuid id PK
      varchar email UK
      varchar timezone
      varchar price_color_scheme
      timestamptz created_at
    }

    PORTFOLIOS {
      uuid id PK
      uuid user_id FK
      varchar name
      boolean is_default
      timestamptz created_at
    }

    TRANSACTIONS {
      uuid id PK
      uuid portfolio_id FK
      uuid security_id FK
      varchar transaction_type
      timestamptz transaction_time
      bigint quantity_shares
      numeric price
      numeric fee
      varchar lot_type
      timestamptz created_at
      timestamptz updated_at
    }

    POSITIONS {
      uuid portfolio_id FK
      uuid security_id FK
      bigint quantity_shares
      numeric average_cost
      numeric cost_basis
      numeric realized_pnl
      timestamptz recalculated_at
    }

    POSITION_SNAPSHOTS {
      uuid portfolio_id FK
      uuid security_id FK
      date snapshot_date
      bigint quantity_shares
      numeric average_cost
      numeric close_price
      numeric market_value
      numeric unrealized_pnl
      numeric realized_pnl
    }

    WATCHLISTS {
      uuid id PK
      uuid user_id FK
      varchar name
      integer sort_order
    }

    WATCHLIST_ITEMS {
      uuid id PK
      uuid watchlist_id FK
      uuid security_id FK
      integer sort_order
      text note
      numeric target_price
      numeric stop_price
      numeric add_price
    }

    ALERT_RULES {
      uuid id PK
      uuid user_id FK
      varchar target_type
      varchar target_id
      varchar rule_type
      jsonb parameters
      integer cooldown_minutes
      integer daily_limit
      boolean is_enabled
    }

    ALERT_EVENTS {
      uuid id PK
      uuid alert_rule_id FK
      timestamptz triggered_at
      jsonb observed_values
      varchar deduplication_key
      varchar delivery_status
    }

    NOTIFICATIONS {
      uuid id PK
      uuid user_id FK
      uuid alert_event_id FK
      varchar category
      varchar title
      text body
      boolean is_read
      timestamptz created_at
    }

    SAVED_SCREENERS {
      uuid id PK
      uuid user_id FK
      varchar name
      jsonb expression
      boolean notification_enabled
    }
```

## 5. 投資組合計算規則

### 5.1 買進

```text
new_quantity = old_quantity + buy_quantity
new_cost_basis = old_cost_basis + buy_quantity × buy_price + fee
new_average_cost = new_cost_basis / new_quantity
```

### 5.2 賣出

MVP 移動平均成本：

```text
sold_cost = sell_quantity × old_average_cost
realized_pnl = sell_quantity × sell_price - fee - sold_cost
remaining_quantity = old_quantity - sell_quantity
remaining_cost_basis = old_cost_basis - sold_cost
```

限制：

- `sell_quantity <= old_quantity`。
- 全數賣出後 quantity、average_cost、cost_basis 歸零。
- 稅額不由使用者輸入，MVP 不納入。
- 修改或刪除歷史交易後，由最早受影響日期開始重算。

## 6. Alert Rule JSON 範例

```json
{
  "rule_type": "PRICE_NEAR_MA",
  "target_type": "SECURITY",
  "target_id": "security-uuid",
  "parameters": {
    "ma_period": 20,
    "distance_percent": 0.5,
    "price_basis": "LAST"
  },
  "cooldown_minutes": 120,
  "daily_limit": 2
}
```

```json
{
  "rule_type": "FOREIGN_FUTURES_NET_OI_CHANGE",
  "target_type": "FUTURES_PRODUCT",
  "target_id": "TX",
  "parameters": {
    "operator": "LTE",
    "threshold_contracts": -5000
  },
  "cooldown_minutes": 1440,
  "daily_limit": 1
}
```

## 7. 主要索引

- `securities(market_id, code)` unique。
- `daily_prices(security_id, trade_date)` unique。
- `intraday_bars(security_id, interval_minutes, bar_time)` unique。
- `institution_spot_trading(security_id, trade_date, institution_type, dealer_subtype)` unique。
- `margin_trading(security_id, trade_date)` unique。
- `securities_lending(security_id, trade_date)` unique。
- `institution_futures_positions(product_id, trade_date, institution_type)` unique。
- `transactions(portfolio_id, transaction_time, id)`。
- `alert_events(alert_rule_id, triggered_at)`。
- `alert_events(deduplication_key)` unique where appropriate。
- PostgreSQL trigram index：`securities.name`、`themes.name`。

## 8. Data Quality 欄位

行情、法人、信用及衍生品表應額外具備：

- `source_code`
- `as_of`
- `received_at`
- `data_status`
- `source_revision`
- `ingestion_run_id`

`data_status`：

- `LIVE`
- `DELAYED`
- `PRELIMINARY`
- `FINAL`
- `STALE`
- `PARTIAL`
- `UNAVAILABLE`
