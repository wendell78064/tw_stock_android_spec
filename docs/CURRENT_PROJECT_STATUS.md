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
```

- Current phase: **Phase 5 / Slice 1 — COMPLETE** (Software Foundation)
- Production Realtime Provider: **UNCONFIGURED**
- DB head: `0011_stock_screener`
- Room: version 9
- Latest tag: `phase-5-slice-1-complete`
- GitHub Actions CI: **PASS** (Run 31670900266)

## Phase 5 / Slice 1 Completed Features

- Realtime provider abstraction (`RealtimeMarketDataProvider`)
- Capability and license boundary (`ProviderCapabilities`)
- Fake realtime provider (`FakeRealtimeProvider`) & safe placeholder (`UnconfiguredRealtimeProvider`)
- Redis realtime cache (TTL 120s, out-of-order rejection) & Pub/Sub channel
- WebSocket quote transport (`/v1/ws/quotes`, Protocol v1, max 100 securities/connection, 100ms coalescing)
- HTTP snapshot & batch APIs (`GET /v1/quotes/{market}/{code}`, `POST /v1/quotes/batch`, `GET /v1/quotes/health`)
- Android realtime client (`RealtimeQuoteClient` with OkHttp WebSocket & exponential backoff)
- Shared subscription manager (`RealtimeSubscriptionManager` with reference counting)
- Security Detail LIVE price integration

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Phase 5 / Slice 2 — Intraday Quote + 1m/5m K

Do not start Slice 2 without explicit request and Slice definition.

## Primary References

- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
