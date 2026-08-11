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
```

- Current phase：Phase 3 / Slice 3 COMPLETE
- Latest completed feature：Alert Engine + Notification Center
- Feature commit：`509a753f4d454b57108c167ca9414f35739faab1`
- DB head：`0008_alert_engine`
- Latest tags：`phase-3-slice-3-complete`、`phase-3-complete`
- GitHub Actions：backend／android／android-instrumentation PASS

## Completed Personal-Investment Core

### Portfolio

- BUY／SELL
- Moving average cost
- Positions
- Realized／unrealized P&L
- Market value
- Portfolio summary

### Watchlist

- Multiple groups and item CRUD
- Target／Stop／Add price
- Market／technical／institutional／credit enrichment
- Room offline cache

### Alert

- SECURITY／PORTFOLIO／WATCHLIST scopes
- Price alerts
- MA5／10／20／60／120／240
- Near／Touch
- Cross Above／Below
- Close Above／Below
- Consecutive Above／Below
- Dedup／cooldown／daily limit
- Notification Center
- Read／unread
- Room offline cache

## External and Future

- FCM remote push：`UNCONFIGURED`
- Alert Engine and Notification Center are complete without remote FCM delivery.

## Known External Data Constraints

### TWSE lending availability

- `lending_short_sell`：official OpenAPI supported
- Other required fields：`UNAVAILABLE`／`LICENSE_REQUIRED`
- Missing official fields remain `null`; no scraping or Fake fallback in formal operation.

### TAIWAN VIX licensing

- Official historical download exists, but automated storage／redistribution permission is unverified.
- Formal Provider state：`UNAVAILABLE`／`LICENSE_REQUIRED`
- External licensing does not mark completed software Slices incomplete.

## Next

Phase 4 / Slice 1 — Industry / Theme Foundation

Do not start Phase 4 without a separate explicit request and Slice definition.

## Primary References

- `docs/14_PHASE_3_ALERT_ENGINE.md`
- `docs/13_PHASE_3_WATCHLIST.md`
- `docs/12_PHASE_3_PORTFOLIO_CORE.md`
- `docs/11_PHASE_2_DERIVATIVES.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
