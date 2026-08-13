# Current Project Status

> 後續 Codex Slice 優先閱讀本文件，再依工作範圍讀取直接相關規格與原始碼。

## Completion

```text
Phase 0 COMPLETE
Phase 1 COMPLETE
Phase 2 COMPLETE
Phase 3 COMPLETE
Phase 4 COMPLETE

Phase 4 / Slice 4 COMPLETE
Phase 5 / Slice 1 COMPLETE
Phase 5 / Slice 2 COMPLETE
```

- Current phase: **Phase 5 / Slice 2 — COMPLETE**
- Production Realtime Provider: **UNCONFIGURED**
- DB head: `0011_stock_screener`
- Room: version 9
- Latest tag: `phase-5-slice-2-complete`
- GitHub Actions CI: **PASS** ([Run 31680550147](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31680550147))
- CI jobs: backend **PASS**, android **PASS**, android-instrumentation **PASS**
- CI instrumentation: `connectedDebugAndroidTest` **PASS**, API 35 emulator, 25 tests, 0 skipped/failed
- Local device instrumentation execution: **NOT RUN**

## Phase 5 / Slice 2 Completed Features

- Decimal 1m candles and derived 5m candles using Taiwan exchange local-clock buckets
- Redis current/history/baseline cache with bounded retention and restart/reconnect safety
- HTTP intraday history plus backward-compatible WebSocket candle channels and snapshots
- Android Security Detail 1D chart with 1m/5m switching and incremental live updates
- Intraday Quote Aggregation
- 1m K and 5m K
- Redis intraday history with 5-day retention target
- HTTP intraday API and WebSocket candle updates

## Database

- PostgreSQL: **unchanged** (`0011_stock_screener`)
- Room: **unchanged** (version 9)

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Phase 5 / Slice 3 — Realtime Market / Industry Strength

Do not start Slice 3 without explicit request and Slice definition.

## Primary References

- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/19_PHASE_5_INTRADAY_CANDLES.md`
- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
