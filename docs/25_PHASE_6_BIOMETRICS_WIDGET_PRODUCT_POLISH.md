# Phase 6 / Slice 4 — Biometrics / Widget / Product Polish

狀態：**COMPLETE**

## Overview

Phase 6 Slice 4 delivers the user security layer, home screen widgets, centralized privacy masking, productized settings architecture, and consistent error/loading/empty UX paradigms across Android, while maintaining local-only security boundaries and zero schema changes.

## 1. App Lock & Biometrics Architecture

- **BiometricPrompt Integration**: Integrates official Android `BiometricPrompt` with `BIOMETRIC_STRONG or DEVICE_CREDENTIAL` fallback (allowing system PIN / Pattern / Password).
- **Security Boundary**: Local privacy layer only. Biometric unlock never bypasses JWT tokens or server authorization, and never stores raw biometric templates.
- **Lifecycle-Aware Relock**:
  - Automatically records timestamp on `onAppBackgrounded()`.
  - Configurable timeouts: `IMMEDIATELY` (0 min), `1 min`, `5 min` (default), `15 min`.
  - Immune to screen orientation changes and Compose recomposition.
  - Process death forces relock if App Lock is enabled.
- **Account Isolation**: Logging out purges session tokens and resets widget caches, preventing subsequent accounts or unauthorized users from accessing financial data.

## 2. Privacy Mode & Data Masking

- **Centralized Masking**: `TaiwanMarketFormatter` masks market value, unrealized P&L, percentage, prices, and share counts into `••••••`.
- **Zero Semantics Leakage**: Hidden values are formatted directly as masked strings before rendering, preventing temporary visual flashing or unmasked inspection.

## 3. Android Home Screen Widgets

- **`SummaryWidgetProvider`**:
  - Displays Portfolio Total Market Value, Unrealized P&L, Return %, and `as_of` / `data_status`.
  - Respects `privacy_mode_enabled` and `widget_financials_enabled`.
  - Displays `未登入` and hides assets when logged out.
  - Tapping opens the Portfolio screen in `MainActivity`.
- **`WatchlistWidgetProvider`**:
  - Displays bounded cached watchlist stocks (5–10 rows max, avoiding N+1 and direct socket subscriptions).
  - Tapping opens the Watchlist screen.
- **`WidgetUpdateHelper`**:
  - Dispatches targeted broadcast updates upon local Room updates, login/logout, and background sync.

## 4. Productized Settings Hierarchy

1. **帳號與雲端同步 (Account & Sync)**:
   - Login/Register form, Signed-in status badge (`已同步`, `同步中`, `離線快取`), Logout with destructive confirmation dialog.
2. **安全與應用程式鎖定 (Security & App Lock)**:
   - App Lock toggle, Biometric capability indicator, Require authentication timeout selector.
3. **隱私與桌面小工具 (Privacy & Widgets)**:
   - Privacy Mode toggle, Show personal financial data in widgets toggle.
4. **外觀主題 (Display Theme)**:
   - Follow System / Light / Dark mode selectors.
5. **資料與備份 (Data & Backup)**:
   - Direct shortcuts to Portfolio / Watchlist CSV Import/Export and PDF Reports.
6. **關於與系統診斷 (About & Diagnostics)**:
   - App version, Database schema head (`0014_personal_data_sync`), Room version (`v12`), Realtime status (`UNCONFIGURED`), Copy diagnostic info button (sanitized).

## 5. UI, Accessibility & Number Formatting

- **TaiwanMarketFormatter**: Centralized currency (`NT$ #,##0.00`), shares (`#,##0`), and percentages (`+0.00%`), formatted in `Asia/Taipei` calendar time.
- **Common Components**:
  - `SkeletonBox`: Minimalistic shimmer placeholder.
  - `EmptyStateView`: Semantic description with clear call-to-action button.
  - `ErrorStateView`: Structured error message with retry button.
  - `StatusBadge`: Explicit badges for `即時`, `盤後定盤`, `延遲/盤後`, `離線快取`.
- **Accessibility**: Minimum touch targets >= 48dp, semantic content descriptions across status badges and forms.

## 6. Database & Room Status

- **PostgreSQL Head**: `0014_personal_data_sync` (No migration required; App lock, privacy mode, and widget preferences are stored device-locally in `SharedPreferences`).
- **Room DB Version**: `v12` (Directly reads cached summaries and watchlist items from existing Room tables).

## 7. CI & Verification

- **GitHub Actions CI Run**: `31776152277`
- **Backend Job**: **PASS** (42s, 136 pytests passed)
- **Android Job**: **PASS** (5m45s, unit tests & lint passed)
- **Android Instrumentation Job**: **PASS** (5m33s, 25 tests on emulator-5554 Android 15, 0 skipped, 0 failed)
- **App Lock & Timeout Smoke**: **PASS**
- **Privacy Masking (`••••••`) Smoke**: **PASS**
- **Home Screen Widgets & Updates Smoke**: **PASS**

