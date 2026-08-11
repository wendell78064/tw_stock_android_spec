# Current Project Status

> 後續 Codex Slice 優先閱讀本文件，再依工作範圍讀取直接相關規格與原始碼。

## Completion

```text
Phase 0 COMPLETE
Phase 1 COMPLETE
Phase 2 COMPLETE
Phase 3 COMPLETE

Phase 3 / Slice 1 COMPLETE
Phase 3 / Slice 2 COMPLETE
Phase 3 / Slice 3 COMPLETE
Phase 4 / Slice 1 COMPLETE
```

- Current phase: Phase 4 / Slice 1 COMPLETE
- Latest completed feature: Industry & Theme Foundation
- Feature commit: `41a7cc4`
- DB head: `0009_industry_theme_foundation`
- Room: version 8
- Latest tag: `phase-4-slice-1-complete`
- GitHub Actions: backend / android / android-instrumentation PASS (connectedDebugAndroidTest 15 tests PASS on API 35 / Google APIs / x86_64)

## Completed Features

### Portfolio

- BUY / SELL transactions
- Moving average cost
- Positions
- Realized / unrealized P&L
- Market value
- Portfolio summary

### Watchlist

- Multiple groups and item CRUD
- Target / Stop / Add price
- Market / technical / institutional / credit enrichment
- Room offline cache

### Alert

- SECURITY / PORTFOLIO / WATCHLIST scopes
- Price alerts
- MA5 / 10 / 20 / 60 / 120 / 240
- Near / Touch / Cross / Close / Consecutive
- Dedup / cooldown / daily limit
- Notification Center
- Read / unread
- Room offline cache

### Industry & Theme Foundation (Phase 4 / Slice 1)

- Official Industry (TWSE taxonomy)
- Custom Theme (dynamic non-enum classifications)
- Security multi-theme mapping
- Industry / Theme APIs
- Admin protected Theme CRUD (`X-Admin-Key`)
- Bulk member market enrichment (SQL window function)
- Industry Android navigation ("產業" bottom tab)
- Industry / Theme detail screens
- Security Detail Industry & Theme tags
- Room offline / STALE cache (`MIGRATION_7_8`)

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Phase 4 / Slice 2 — Industry Strength Ranking

Do not start Phase 4 / Slice 2 without a separate explicit request and Slice definition.

## Primary References

- `docs/14_PHASE_3_ALERT_ENGINE.md`
- `docs/13_PHASE_3_WATCHLIST.md`
- `docs/12_PHASE_3_PORTFOLIO_CORE.md`
- `docs/11_PHASE_2_DERIVATIVES.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
