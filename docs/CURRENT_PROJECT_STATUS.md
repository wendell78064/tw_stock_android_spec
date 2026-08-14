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
Phase 6 / Slice 4 COMPLETE
```

- Current: **Phase 6 / Slice 4 — COMPLETE**
- Previous: **Phase 6 / Slice 3 COMPLETE**
- Database: `0014_personal_data_sync`
- Room: version 12
- Production Realtime Provider: `UNCONFIGURED`
- FCM: `UNCONFIGURED`
- Latest tag: `phase-6-slice-4-complete`
- GitHub Actions CI: **PASS** ([Run 31776152277](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31776152277))
- CI jobs: backend **PASS**, android **PASS**, android-instrumentation **PASS**

## Phase 6 / Slice 4 Completed Features

- Official Android `BiometricPrompt` & Device Credential fallback (`AppLockManager`)
- Lifecycle-aware background relock with configurable timeouts (`0`, `1`, `5`, `15` min)
- Privacy Mode masking (`••••••`) in UI and Home Screen Widgets
- Home Screen Widgets: `SummaryWidgetProvider` and `WatchlistWidgetProvider` reading Room caches
- Productized Settings screen: Account & Sync, Security, Privacy, Widgets, Theme, and Diagnostics
- Common UI components: `SkeletonBox`, `EmptyStateView`, `ErrorStateView` with retry, `StatusBadge`
- Centralized `TaiwanMarketFormatter` handling prices, shares, amounts, and `Asia/Taipei` dates

## Database

- PostgreSQL: `0014_personal_data_sync`
- Room: version 12

## External and Future

- Production Realtime Provider: `UNCONFIGURED`
- FCM remote push: `UNCONFIGURED`

## Next

Phase 6 / Slice 5 — AI / Production Integration Hardening

Do not start Slice 5 without explicit request.

## Primary References

- `docs/25_PHASE_6_BIOMETRICS_WIDGET_PRODUCT_POLISH.md`
- `docs/24_PHASE_6_IMPORT_EXPORT_REPORTS.md`
- `docs/23_PHASE_6_PERSONAL_DATA_SYNC.md`
- `docs/22_PHASE_6_ACCOUNT_CLOUD_SYNC_FOUNDATION.md`
