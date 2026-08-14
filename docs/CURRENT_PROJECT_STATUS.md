# Current Project Status

> 後續 Codex Slice 優先閱讀本文件，再依工作範圍讀取直接相關規格與原始碼。

## Completion

```text
Phase 0 COMPLETE
Phase 1 COMPLETE
Phase 2 COMPLETE
Phase 3 COMPLETE
Phase 4 COMPLETE
Phase 5 SOFTWARE COMPLETE

Phase 6 / Slice 1 COMPLETE
Phase 6 / Slice 2 COMPLETE
```

- Current: **Phase 6 / Slice 2 — COMPLETE**
- Previous: **Phase 6 / Slice 1 COMPLETE**
- Database: `0014_personal_data_sync`
- Room: version 12
- Production Realtime Provider: `UNCONFIGURED`
- FCM: `UNCONFIGURED`
- Latest tag: `phase-6-slice-2-complete`
- GitHub Actions CI: **PASS** ([Run 31768268218](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31768268218))
- CI jobs: backend **PASS**, android **PASS**, android-instrumentation **PASS**

## Phase 6 / Slice 2 Completed Features

- Portfolio & canonical transaction sync (excluding derived metrics)
- Alert rule configuration sync & scope referential integrity
- Saved screener AST sync & validation
- User settings sync (with device-local forbidden key security gating)
- Shared Outbox / Cursor / Tombstone / Version / Conflict pipeline
- Account isolation & cross-device purge on logout
- Room runtime migration v10 → v11, v11 → v12, and chained v10 → v12 (PASS)

## Database

- PostgreSQL: `0014_personal_data_sync`
- Room: version 12

## External and Future

- Production Realtime Provider: `UNCONFIGURED`
- FCM remote push: `UNCONFIGURED`

## Next

Phase 6 / Slice 3 — Import / Export / Reports

Do not start Slice 3 without explicit request.

## Primary References

- `docs/23_PHASE_6_PERSONAL_DATA_SYNC.md`
- `docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md`
- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
