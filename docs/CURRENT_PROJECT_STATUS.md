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
Phase 6 / Slice 3 COMPLETE
```

- Current: **Phase 6 / Slice 3 — Import / Export / Reports**
- Previous: **Phase 6 / Slice 2 COMPLETE**
- Database: `0014_personal_data_sync`
- Room: version 12
- Production Realtime Provider: `UNCONFIGURED`
- FCM: `UNCONFIGURED`
- Latest tag: `phase-6-slice-2-complete`

## Phase 6 / Slice 3 Completed Features

- Portfolio transactions, holdings, and summary CSV export (UTF-8 BOM, Decimal precision, Taipei timezone)
- Watchlists CSV export
- Formula injection escaping policy (`=`, `+`, `-`, `@`)
- Portfolio report PDF generation
- Two-phase import workflow (Dry-run preview with validation & Confirmed atomic apply)
- Chronological accounting replay & oversell rejection
- Duplicate detection & re-import idempotency
- Cloud Sync integration (`SyncChangeModel` sequence and version increments)
- Android SAF file picker integration & ViewModels

## Database

- PostgreSQL: `0014_personal_data_sync`
- Room: version 12

## External and Future

- Production Realtime Provider: `UNCONFIGURED`
- FCM remote push: `UNCONFIGURED`

## Next

Phase 6 / Slice 4 — Biometrics / Widget / Product Polish

Do not start Slice 4 without explicit request.

## Primary References

- `docs/24_PHASE_6_IMPORT_EXPORT_REPORTS.md`
- `docs/23_PHASE_6_PERSONAL_DATA_SYNC.md`
- `docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`

