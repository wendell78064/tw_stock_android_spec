# 16 — Phase 4 / Slice 3: Stock Screener

狀態：**COMPLETE**

## Overview

The Multi-Condition Stock Screener enables flexible, deterministic cross-sectional filtering across all security attributes in the TW Stock ecosystem (Price/Return, Technicals, Institutional Trading, Credit/Margin Trading, Taxonomy, and Industry Strength).

## Architectural & Field Design

- **Typed Screener AST**: Supports nested `CONDITION`, `AND`, and `OR` nodes via `ScreenerExpression`.
- **Field Whitelist Catalog**: Exposed via `GET /v1/screener/fields` using `SCREENER_FIELDS_REGISTRY` in `app.domain.screener`.
- **Missing Data Semantics**:
  - `null` values evaluate to `NON_MATCH` for comparisons (`GT`, `LT`, `BETWEEN`, `EQ`, `IN`).
  - `IS_UNAVAILABLE` evaluates to `MATCH` for missing values, while `IS_AVAILABLE` requires non-null.
- **Bulk Execution Engine**: `ScreenerQueryService` executes single-pass bulk SQL joins over active securities for the target `trade_date`, avoiding N+1 roundtrips.

## Saved Screener & Persistence

- **Database Migration**: `0011_stock_screener` creates `saved_screeners` table (JSONB AST expression).
- **CRUD Endpoints**: `/v1/screeners` (Create, List, Get, Patch, Delete, Run).
- **Android Offline Cache**: Room database cache for saved screeners, field metadata, and last query results with `STALE` status indicator.

## Validation & CI Status

- GitHub CI: PASS
- backend: PASS
- android: PASS
- android-instrumentation: PASS
- connectedDebugAndroidTest: PASS
- Android API 35 / Google APIs / x86_64
- Backend unit tests (`tests/test_screener.py`): AST validation, invalid operator/field rejection, AST dict conversion, API endpoints PASS.
- Android unit & UI tests (`feature-screener`): Repository caching, ViewModel builder logic, Compose rendering PASS.
