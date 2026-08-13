# 17 — Phase 4 / Slice 4: Stock Comparison

狀態：**COMPLETE**

## Overview

The Stock Comparison module allows users to select 2 to 5 securities (across TWSE and TPEx markets) and analyze their normalized price performance, fundamental/technical metrics, and deterministic objective divergence signals.

## Features & Implementation

- **Selection Rules & Validation**: Supports 2–5 securities (`INVALID_SELECTION_COUNT`, `DUPLICATE_SECURITY_SELECTION`, `SECURITY_NOT_FOUND`).
- **Normalized Performance Chart (Base 100)**: Normalizes close prices (`normalized_value = close / first_valid_close * 100`) using common trading date intersections.
- **Comparison Windows**: Supports 1D, 5D, 10D, 20D, 60D, 1Y, and 5Y windows.
- **Metrics Aggregation**: Price/Return, Technicals (MA, RSI14, MACD, KD), Institutional net flows (Foreign, Trust, Dealer), Credit trading (Margin, Short, Lending), Taxonomy, and Industry Strength.
- **Objective Divergence Signals**: Deterministic non-promotional signals (`PRICE_OUTPERFORMANCE`, `PRICE_UNDERPERFORMANCE`, `INSTITUTIONAL_DIVERGENCE`, `TECHNICAL_DIVERGENCE`) based on `ComparisonSignalConfig` thresholds.

## API Endpoints

- `POST /v1/comparisons/run`: Runs multi-security comparison query.

## Persistence & Migration

- No DB migration required for this slice. DB head remains `0011_stock_screener`.

## Validation & Test Coverage

- **Backend Unit Tests**: `tests/test_comparison.py` (Selection validation, deterministic thresholds).
- **Android Unit Tests**: `feature-comparison/src/test/.../ComparisonTests.kt` (Selection limits, ViewModel flow).
- **Android Instrumentation Tests**: `app/src/androidTest/.../ComparisonInstrumentationTest.kt` (Full UI rendering).

## CI Record

GitHub Actions Run: **31667324690**

| Job | Result |
|-----|--------|
| backend | PASS |
| android | PASS |
| android-instrumentation | PASS |

## CI Stabilization Fixes

These fixes were made to stabilise CI after the initial implementation commit.
They are infrastructure / linting corrections, not product feature changes.

- **Ruff E501**: Wrapped all lines exceeding 100 chars in `comparison.py` and `api/comparison.py`.
- **Ruff B023**: Extracted inner `calc_return` closure to standalone `_return_for()` helper to properly capture loop variables.
- **Ruff F821**: Moved `comparison_service` dependency function below `database_session` to resolve forward-reference.
- **Ruff B008**: Replaced `ComparisonSignalConfig()` default argument with `None` sentinel initialised inside function body.
- **Ruff F841**: Renamed unused `strengths` assignment to `_`.
- **pytest DB fixture**: Switched `test_comparison.py` to use `dependency_overrides` with `AsyncMock` session instead of relying on `app.state.session_factory`.
- **Robolectric offline Maven**: Removed `@RunWith(RobolectricTestRunner::class)` / `@Config(sdk=[34])` and Robolectric/ui-test deps from `feature-comparison`; tests converted to pure JUnit4 + coroutines-test which does not require SDK artifact download.

