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
Phase 5 / Slice 4 COMPLETE
Phase 5 SOFTWARE COMPLETE
Phase 6 / Slice 1 COMPLETE (local validation; CI pending)
```

- Current: **Phase 6 / Slice 1 — Account / Cloud Sync Foundation**
- Previous: **Phase 5 SOFTWARE COMPLETE**
- Production Realtime Provider: **UNCONFIGURED**
- DB head: `0013_account_sync_foundation`
- Room: version 11
- Latest tags: `phase-5-slice-4-complete`, `phase-5-software-complete`
- GitHub Actions CI: **PASS** ([Run 31684839240](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31684839240))
- CI jobs: backend **PASS**, android **PASS**, android-instrumentation **PASS**
- CI instrumentation: `connectedDebugAndroidTest` **PASS**, API 35 emulator, 25 tests, 0 skipped/failed
- Local device instrumentation execution: **NOT RUN**

## Phase 5 Software Completed

- Slice 1: Realtime Provider / WebSocket Foundation
- Slice 2: Intraday 1m / 5m Candles
- Slice 3: Realtime Market / Industry Strength
- Slice 4: Realtime Alert Engine

## Database

- PostgreSQL: **changed** (`0012_realtime_alert_engine`)
- Room: **unchanged** (version 10)

## External and Future

- Production Realtime Provider: `UNCONFIGURED`
- FCM remote push: `UNCONFIGURED`
- External production gates: authorized realtime data provider, redistribution/license confirmation, and FCM configuration if remote push is required.
- Phase 5 is **software complete**, not production realtime ready.

## Next

Complete Phase 6 / Slice 1 CI validation before starting Slice 2.

## Primary References

- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/19_PHASE_5_INTRADAY_CANDLES.md`
- `docs/20_PHASE_5_REALTIME_MARKET_INDUSTRY_STRENGTH.md`
- `docs/21_PHASE_5_REALTIME_ALERT_ENGINE.md`
- `docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md`
- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
