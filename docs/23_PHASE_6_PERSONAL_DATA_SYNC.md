# Phase 6 / Slice 2 — Portfolio / Alerts / Screener / Settings Sync

狀態：**COMPLETE**

## Overview

Phase 6 Slice 2 extends the single durable cloud synchronization architecture across all personal user domains: Portfolios, Portfolio Transactions, Alert Rules, Saved Screeners, and User Settings.

## Synchronized Personal Domains

### 1. Portfolio & Portfolio Transactions
- **Portfolios**: Synchronizes portfolio entity (`id`, `name`, `base_currency`, `is_default`, `version`, `deleted_at`).
- **Portfolio Transactions**: Synchronizes canonical transaction log (`portfolio_id`, `security_id`, `side`, `executed_at`, `quantity_shares`, `price`, `fee`, `lot_type`).
- **Excluded Derived State**: Position units, average cost basis, market value, unrealized P&L, and realized P&L are **deliberately excluded** from sync payloads and recalculated locally from canonical transaction entities.
- **Optimistic Concurrency**: Stale version update/delete attempts return `CONFLICT` with `server_version` and canonical server transaction details.

### 2. Alert Rules
- **Configuration Sync**: Synchronizes alert configuration (`name`, `rule_type`, `scope_type`, `security_id`, `portfolio_id`, `watchlist_id`, `threshold_price`, `threshold_percent`, `ma_period`, `consecutive_days`, `cooldown_minutes`, `daily_limit`, `enabled`, `evaluation_mode`, `session_scope`).
- **Scope Referential Integrity**: Resolves scope dependencies across Securities, Portfolios, and Watchlists. Missing scope references reject corrupted payloads.
- **Excluded Transient State**: Dynamic Redis realtime state, transient quotes, and moving average cache are excluded.

### 3. Saved Screeners
- **Screener Definition Sync**: Synchronizes id, name, description, expression AST, sort field, and sort direction.
- **AST Re-Validation**: Saved Screener AST expressions are strictly validated server-side. Non-dict expressions or invalid structures return `REJECTED`.

### 4. User Settings
- **Syncable Preferences**: Synchronizes cross-device UI preferences, chart indicators, and default settings.
- **Device-Local Settings Security Boundary**: Device-local sensitive keys (`auth_token`, `device_id`, `refresh_token`, `notification_permission_state`, `os_setting`) are explicitly rejected (`FORBIDDEN_SETTING_KEYS`).

## Synchronization Engine & Account Isolation

- **Shared Protocol**: Reuses the durable Outbox, Cursor, Tombstone, Version, and Optimistic Conflict pipeline established in Slice 1.
- **Deterministic Pull & Apply Order**: `WATCHLIST` → `WATCHLIST_ITEM` → `PORTFOLIO` → `PORTFOLIO_TRANSACTION` → `ALERT_RULE` → `SAVED_SCREENER` → `USER_SETTING`.
- **Account Isolation**: Switching accounts or logging out purges all personal SQLite cache tables (`cloud_portfolio_cache`, `cloud_portfolio_transaction_cache`, `cloud_alert_rule_cache`, `cloud_saved_screener_cache`, `cloud_user_setting_cache`, `cloud_watchlist_cache`, `cloud_watchlist_item_cache`, outbox, and cursor).

## Database & Migration Status

- **PostgreSQL Migration Head**: `0014_personal_data_sync`
- **Room Database Version**: `v12` (`MIGRATION_11_12`)
- **Room Runtime Migration**:
  - `v10 → v11`: PASS (verified in `RoomMigration10To11Test.kt`)
  - `v11 → v12`: PASS (verified in `RoomMigration11To12Test.kt`)
  - `v10 → v12` chained: PASS (verified in `RoomMigration11To12Test.kt`)

## CI Validation

GitHub Actions Run: **31768268218**
Feature Commit: `3471ed4`
Final CI Commit: `cfe0c83`

| Job | Result |
|-----|--------|
| backend | PASS |
| android | PASS |
| android-instrumentation | PASS |

- **API Level**: 35 (`google_apis`, `x86_64` emulator)
- **Local Device Execution**: NOT RUN
