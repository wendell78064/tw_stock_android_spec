# Phase 6 / Slice 3 — Import / Export / Reports

狀態：**COMPLETE**

## Overview

Phase 6 Slice 3 implements personal data portability, batch migration, and financial reporting across Portfolios, Portfolio Transactions, Watchlists, and PDF Reports, strictly adhering to server-authoritative validation, cloud sync change logging, and formula injection security boundaries.

## Canonical CSV Formats & Specifications

### 1. Portfolio Transactions CSV (`twml-portfolio-csv-v1`)
- **Encoding**: UTF-8 with UTF-8 BOM (`\ufeff`) for Microsoft Excel CJK compatibility.
- **Header**:
  ```csv
  format_version,transaction_id,portfolio_name,market,code,side,trade_date,trade_time,shares,price,fee,lot_type
  ```
- **Fields**:
  - `format_version`: `twml-portfolio-csv-v1`
  - `transaction_id`: Canonical UUID string (preserves idempotency on re-import)
  - `portfolio_name`: Escaped user portfolio label
  - `market`: `TWSE` or `TPEX`
  - `code`: Valid stock code
  - `side`: `BUY` or `SELL`
  - `trade_date`: `YYYY-MM-DD` (`Asia/Taipei` calendar date)
  - `trade_time`: `HH:mm:ss` (`Asia/Taipei` execution time)
  - `shares`: Integer share count (e.g. `1000`)
  - `price`: Exact decimal string without scientific notation
  - `fee`: Exact decimal fee
  - `lot_type`: `BOARD_LOT` or `ODD_LOT`

### 2. Portfolio Holdings CSV
- **Header**: `market,code,name,shares,average_cost,latest_price,market_value,unrealized_pnl,unrealized_pnl_pct`
- Derived report representing point-in-time holdings breakdown.

### 3. Portfolio Summary CSV
- **Header**: `portfolio_name,as_of,total_cost,market_value,realized_pnl,unrealized_pnl,total_pnl,position_count,data_status`
- Summary metric export with explicit `data_status` (`FINAL`, `PARTIAL`, `STALE`).

### 4. Watchlists CSV (`twml-watchlist-csv-v1`)
- **Header**:
  ```csv
  format_version,group_id,group_name,group_order,market,code,item_order,note,target_price,stop_price,add_price
  ```

## Security & Safety Boundaries

- **Spreadsheet Formula Injection**: All string cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` are safely escaped with a leading single quote (`'`) upon export and normalized on import.
- **No Secrets Export**: Access tokens, refresh tokens, password hashes, device IDs, sync cursors, and transient Redis states are strictly excluded.
- **Strict User Scope**: All export and import endpoints require authenticated Bearer credentials. Cross-user data access is strictly forbidden (`404 PORTFOLIO_NOT_FOUND`).
- **File Upload Limits**: Maximum 5 MB payload size and 10,000 rows per batch.

## Two-Phase Import Architecture

1. **Dry-Run / Preview (`POST /v1/imports/portfolio/preview` & `POST /v1/imports/watchlists/preview`)**:
   - Parses CSV and performs strict Decimal, date, and security resolution (`market + code` or unambiguous `code`).
   - Replays chronological accounting to verify that sell transactions do not result in negative holdings (`OVERSELL` error).
   - Generates transient `preview_token` stored in Redis with a 30-minute TTL.
   - Returns statistics (`total_rows`, `valid_rows`, `invalid_rows`, `warning_rows`, `duplicate_rows`) and row-by-row error reports.
2. **Confirmed Apply (`POST /v1/imports/portfolio/apply` & `POST /v1/imports/watchlists/apply`)**:
   - Atomically commits all validated operations (all-or-nothing).
   - Emits `SyncChangeModel` records with monotonic sequence numbers and version increments so peer devices pull changes automatically.
   - Preserves idempotency for existing transaction UUIDs (`skipped_count`).

## PDF Portfolio Report

- **Endpoint**: `GET /v1/reports/portfolio/{portfolio_id}.pdf`
- **Content**: Title (`TW Market Ledger Portfolio Report`), Portfolio Name, Generation Timestamp (`Asia/Taipei`), Data Status, Cost Basis, Market Value, Realized & Unrealized P&L, Active Positions Table, and Allocation.
- **Font & Rendering**: Standard PDF output with deterministic fallback.

## Android Architecture

- **`ImportExportApi`**: Retrofit client with `@Streaming` response bodies and multipart/JSON import endpoints.
- **ViewModels**: `PortfolioImportExportViewModel` and `WatchlistImportExportViewModel` managing UI states (`Idle`, `Loading`, `PreviewReady`, `ExportReady`, `ApplySuccess`, `Error`).
- **Storage Access Framework (SAF)**: Integrates via `ACTION_OPEN_DOCUMENT` and `ACTION_CREATE_DOCUMENT` without requiring broad external storage permissions.

## Database Status

- **PostgreSQL Head**: `0014_personal_data_sync` (No migration required; utilizes Redis for preview tokens and existing tables with sync change log).
- **Room DB Version**: `v12`
