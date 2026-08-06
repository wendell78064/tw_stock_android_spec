-- Core PostgreSQL schema baseline.
-- Use Alembic migrations in the actual backend. This file is a reference starting point.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE data_status AS ENUM (
  'LIVE', 'DELAYED', 'PRELIMINARY', 'FINAL', 'STALE', 'PARTIAL', 'UNAVAILABLE'
);

CREATE TYPE transaction_type AS ENUM ('BUY', 'SELL');
CREATE TYPE lot_type AS ENUM ('BOARD_LOT', 'ODD_LOT');
CREATE TYPE institution_type AS ENUM ('FOREIGN', 'INVESTMENT_TRUST', 'DEALER', 'TOTAL');

CREATE TABLE markets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(16) NOT NULL UNIQUE,
  name varchar(80) NOT NULL,
  timezone varchar(64) NOT NULL DEFAULT 'Asia/Taipei'
);

CREATE TABLE securities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL REFERENCES markets(id),
  code varchar(16) NOT NULL,
  name varchar(120) NOT NULL,
  security_type varchar(32) NOT NULL DEFAULT 'COMMON_STOCK',
  is_active boolean NOT NULL DEFAULT true,
  listing_date date,
  delisting_date date,
  shares_outstanding bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (market_id, code)
);

CREATE INDEX securities_name_trgm_idx ON securities USING gin (name gin_trgm_ops);

CREATE TABLE industries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(32) NOT NULL UNIQUE,
  name varchar(120) NOT NULL,
  classification_source varchar(32) NOT NULL
);

CREATE TABLE themes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug varchar(80) NOT NULL UNIQUE,
  name varchar(120) NOT NULL,
  description text
);

CREATE TABLE security_industries (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  industry_id uuid NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
  is_primary boolean NOT NULL DEFAULT false,
  PRIMARY KEY (security_id, industry_id)
);

CREATE TABLE security_themes (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  theme_id uuid NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
  relevance_weight numeric(8,4),
  PRIMARY KEY (security_id, theme_id)
);

CREATE TABLE daily_prices (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  open numeric(20,6) NOT NULL,
  high numeric(20,6) NOT NULL,
  low numeric(20,6) NOT NULL,
  close numeric(20,6) NOT NULL,
  adjusted_close numeric(20,6),
  volume_shares bigint,
  turnover_amount numeric(24,4),
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  source_revision varchar(64),
  ingestion_run_id uuid,
  PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE technical_snapshots (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  price_basis varchar(16) NOT NULL DEFAULT 'ADJUSTED',
  ma5 numeric(20,6),
  ma10 numeric(20,6),
  ma20 numeric(20,6),
  ma60 numeric(20,6),
  ma120 numeric(20,6),
  ma240 numeric(20,6),
  rsi14 numeric(20,8),
  macd numeric(20,8),
  macd_signal numeric(20,8),
  macd_histogram numeric(20,8),
  kd_k numeric(20,8),
  kd_d numeric(20,8),
  atr14 numeric(20,8),
  obv numeric(28,4),
  PRIMARY KEY (security_id, trade_date, price_basis)
);

CREATE TABLE institution_spot_trading (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  institution institution_type NOT NULL,
  dealer_subtype varchar(16) NOT NULL DEFAULT '',
  buy_amount numeric(24,4),
  sell_amount numeric(24,4),
  net_amount numeric(24,4),
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  PRIMARY KEY (security_id, trade_date, institution, dealer_subtype)
);

CREATE TABLE margin_trading (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  margin_buy bigint,
  margin_sell bigint,
  margin_cash_repayment bigint,
  margin_balance bigint,
  short_sell bigint,
  short_cover bigint,
  short_stock_repayment bigint,
  short_balance bigint,
  margin_utilization numeric(12,6),
  short_utilization numeric(12,6),
  short_margin_ratio numeric(12,6),
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE securities_lending (
  security_id uuid NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  lending_sell bigint,
  lending_return bigint,
  lending_balance bigint,
  lending_balance_change bigint,
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  PRIMARY KEY (security_id, trade_date)
);

CREATE TABLE futures_products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(32) NOT NULL UNIQUE,
  name varchar(120) NOT NULL,
  contract_multiplier numeric(20,6),
  session_type varchar(16)
);

CREATE TABLE futures_contracts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid NOT NULL REFERENCES futures_products(id),
  contract_code varchar(32) NOT NULL UNIQUE,
  expiry_date date NOT NULL,
  is_near_month boolean NOT NULL DEFAULT false,
  is_next_month boolean NOT NULL DEFAULT false
);

CREATE TABLE futures_open_interest (
  contract_id uuid NOT NULL REFERENCES futures_contracts(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  open_interest bigint,
  open_interest_change bigint,
  settlement_price numeric(20,6),
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  PRIMARY KEY (contract_id, trade_date)
);

CREATE TABLE institution_futures_positions (
  product_id uuid NOT NULL REFERENCES futures_products(id) ON DELETE CASCADE,
  trade_date date NOT NULL,
  institution institution_type NOT NULL,
  long_oi bigint,
  short_oi bigint,
  net_oi bigint,
  long_amount numeric(24,4),
  short_amount numeric(24,4),
  net_amount numeric(24,4),
  long_oi_change bigint,
  short_oi_change bigint,
  net_oi_change bigint,
  source_code varchar(32) NOT NULL,
  as_of timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  data_status data_status NOT NULL,
  PRIMARY KEY (product_id, trade_date, institution)
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email varchar(254) NOT NULL UNIQUE,
  timezone varchar(64) NOT NULL DEFAULT 'Asia/Taipei',
  price_color_scheme varchar(32) NOT NULL DEFAULT 'RED_UP_GREEN_DOWN',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE portfolios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name varchar(80) NOT NULL,
  is_default boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id uuid NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  security_id uuid NOT NULL REFERENCES securities(id),
  transaction_type transaction_type NOT NULL,
  transaction_time timestamptz NOT NULL,
  quantity_shares bigint NOT NULL CHECK (quantity_shares > 0),
  price numeric(20,6) NOT NULL CHECK (price >= 0),
  fee numeric(20,6) NOT NULL DEFAULT 0 CHECK (fee >= 0),
  lot_type lot_type NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX transactions_portfolio_time_idx
  ON transactions (portfolio_id, transaction_time, id);

CREATE TABLE positions (
  portfolio_id uuid NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  security_id uuid NOT NULL REFERENCES securities(id),
  quantity_shares bigint NOT NULL DEFAULT 0,
  average_cost numeric(20,6) NOT NULL DEFAULT 0,
  cost_basis numeric(24,6) NOT NULL DEFAULT 0,
  realized_pnl numeric(24,6) NOT NULL DEFAULT 0,
  recalculated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (portfolio_id, security_id)
);

CREATE TABLE watchlists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name varchar(80) NOT NULL,
  sort_order integer NOT NULL DEFAULT 0
);

CREATE TABLE watchlist_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id uuid NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
  security_id uuid NOT NULL REFERENCES securities(id),
  sort_order integer NOT NULL DEFAULT 0,
  note text,
  target_price numeric(20,6),
  stop_price numeric(20,6),
  add_price numeric(20,6),
  UNIQUE (watchlist_id, security_id)
);

CREATE TABLE alert_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_type varchar(32) NOT NULL,
  target_id varchar(128) NOT NULL,
  rule_type varchar(64) NOT NULL,
  parameters jsonb NOT NULL,
  cooldown_minutes integer NOT NULL DEFAULT 120 CHECK (cooldown_minutes >= 0),
  daily_limit integer NOT NULL DEFAULT 2 CHECK (daily_limit > 0),
  is_enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE alert_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_rule_id uuid NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
  triggered_at timestamptz NOT NULL,
  observed_values jsonb NOT NULL,
  deduplication_key varchar(255) NOT NULL,
  delivery_status varchar(32) NOT NULL DEFAULT 'PENDING',
  UNIQUE (deduplication_key)
);

CREATE TABLE ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider varchar(32) NOT NULL,
  dataset varchar(64) NOT NULL,
  trade_date date,
  started_at timestamptz NOT NULL,
  finished_at timestamptz,
  status varchar(16) NOT NULL,
  fetched_count integer NOT NULL DEFAULT 0,
  inserted_count integer NOT NULL DEFAULT 0,
  updated_count integer NOT NULL DEFAULT 0,
  rejected_count integer NOT NULL DEFAULT 0,
  checksum varchar(128),
  error_message text,
  retry_count integer NOT NULL DEFAULT 0
);
