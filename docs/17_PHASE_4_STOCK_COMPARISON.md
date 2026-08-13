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
- **Android Unit Tests**: `feature-comparison/src/test/.../ComparisonTests.kt` (Selection limits, ViewModel flow, Compose rendering).
- **Android Instrumentation Tests**: `app/src/androidTest/.../ComparisonInstrumentationTest.kt` (Full UI rendering).
