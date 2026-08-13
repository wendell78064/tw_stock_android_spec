# Current Project Status

> 後續 Codex Slice 優先閱讀本文件，再依工作範圍讀取直接相關規格與原始碼。

## Completion

```text
Phase 0 COMPLETE
Phase 1 COMPLETE
Phase 2 COMPLETE
Phase 3 COMPLETE
Phase 4 COMPLETE

Phase 3 / Slice 1 COMPLETE
Phase 3 / Slice 2 COMPLETE
Phase 3 / Slice 3 COMPLETE
Phase 4 / Slice 1 COMPLETE
Phase 4 / Slice 2 COMPLETE
Phase 4 / Slice 3 COMPLETE
Phase 4 / Slice 4 COMPLETE
```

- Current phase: **Phase 4 — COMPLETE**
- DB head: `0011_stock_screener`
- Room: version 9
- Latest tag: `phase-4-complete`
- GitHub Actions CI: **PASS** (Run 31667324690)

## Phase 4 Completed Slices

### Slice 1 — Industry / Theme Foundation
- Industry and theme taxonomy, indicator stocks, DB schema, API, Android UI.

### Slice 2 — Industry / Theme Strength Ranking
- Equal-weight and market-cap-weighted strength scores, historical snapshots, Android ranking UI.

### Slice 3 — Stock Screener
- Condition-based screener with AND/OR logic, saved screeners, Android screener builder UI.

### Slice 4 — Stock Comparison
- 2–5 security comparison with selection validation
- Base-100 normalized performance charting (common date intersection)
- Comparison windows: 1D, 5D, 10D, 20D, 60D, 1Y, 5Y
- Technical comparison (MA, RSI14, MACD, KD)
- Institutional net flow comparison (Foreign, Trust, Dealer)
- Credit trading comparison (Margin, Short, Lending)
- Industry / theme membership comparison
- Industry strength comparison
- Deterministic objective divergence signals (PRICE_OUTPERFORMANCE, PRICE_UNDERPERFORMANCE, INSTITUTIONAL_DIVERGENCE, TECHNICAL_DIVERGENCE)
- Android `feature-comparison` UI, ViewModel, NormalizedCanvasChart
- Selected-set internal ranking

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Phase 5 — Realtime / Intraday Market Data

Do not start Phase 5 without a separate explicit request and Slice definition.

## Primary References

- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/16_PHASE_4_STOCK_SCREENER.md`
- `docs/15_PHASE_4_INDUSTRY_THEME_STRENGTH.md`
- `docs/14_PHASE_3_ALERT_ENGINE.md`
- `docs/13_PHASE_3_WATCHLIST.md`
- `docs/12_PHASE_3_PORTFOLIO_CORE.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
