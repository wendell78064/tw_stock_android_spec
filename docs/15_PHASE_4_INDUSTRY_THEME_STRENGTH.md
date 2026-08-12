# 15 — Phase 4 / Slice 2: Industry & Theme Strength Ranking

狀態：**COMPLETE**

## Validation & CI Status

- GitHub CI PASS
- backend PASS
- android PASS
- android-instrumentation PASS
- Local Backend Strength Tests: 32/32 PASS

## Algorithm Specification

Algorithm Version: `twml-industry-strength-v1`

### Component Weights

- **Momentum**: 30% (Equal-weight performance percentile)
- **Breadth**: 20% (Advance ratio percentile)
- **Technical Participation**: 25% (Average of MA20 / MA60 participation percentile)
- **Institutional Flow**: 15% (Net institutional flow sum percentile)
- **Turnover Momentum**: 10% (Turnover momentum percentile)

### Thresholds & Coverage

- Minimum Component Coverage Threshold: 60% (`component_coverage >= 0.60`)
- Ranking is computed cross-sectionally for valid windows (1, 5, 10, 20, 60 trading days).
- Unranked or insufficient coverage snapshots output `strength_score: null`, `rank: null`.

## Deliverables

- **DB Schema & Ingestion**: `0010_industry_strength` DB migration, Alembic support.
- **Backend Service & API**: FastAPI endpoints `/v1/industries/strength`, `/v1/industries/{id}/strength`, `/v1/themes/strength`, `/v1/themes/{id}/strength` with correctly prioritized routing.
- **Android App & Room Cache**: Room DB version 9, UI State, LazyColumn scrolling support, Offline/Stale indicator.
