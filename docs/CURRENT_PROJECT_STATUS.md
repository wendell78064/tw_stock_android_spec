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
Phase 5 / Slice 3 COMPLETE
Phase 5 / Slice 4 IMPLEMENTED — WAITING FOR CI
```

- Current phase: **Phase 5 / Slice 4 — Realtime Alert Engine**
- Production Realtime Provider: **UNCONFIGURED**
- DB head: `0012_realtime_alert_engine`
- Room: version 10
- Latest tag: `phase-5-slice-3-complete`
- GitHub Actions CI: **PASS** ([Run 31683265696](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31683265696))
- CI jobs: backend **PASS**, android **PASS**, android-instrumentation **PASS**
- CI instrumentation: `connectedDebugAndroidTest` **PASS**, API 35 emulator, 25 tests, 0 skipped/failed
- Local device instrumentation execution: **NOT RUN**

## Phase 5 / Slice 4 Implemented

- EOD/REALTIME alert evaluation separation
- Realtime price and dynamic daily MA crossings
- Redis relation state, replay protection, cooldown and daily limit
- Dynamic portfolio/watchlist/security subscription aggregation
- Alert WebSocket channel and realtime status API
- Android realtime rule editor, notification badge and local dedup

## Database

- PostgreSQL: **changed** (`0012_realtime_alert_engine`)
- Room: **unchanged** (version 10)

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Await Phase 5 / Slice 4 CI validation and closeout.

Do not start Slice 4 without explicit request and Slice definition.

## Primary References

- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/19_PHASE_5_INTRADAY_CANDLES.md`
- `docs/20_PHASE_5_REALTIME_MARKET_INDUSTRY_STRENGTH.md`
- `docs/21_PHASE_5_REALTIME_ALERT_ENGINE.md`
- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
