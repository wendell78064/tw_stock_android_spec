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
Phase 5 / Slice 1 IN_PROGRESS
```

- Current phase: **Phase 5 / Slice 1 — Realtime Data Provider + WebSocket Foundation**
- Previous phase: Phase 4 COMPLETE
- Realtime Production Provider: **UNCONFIGURED** (Software foundation complete with deterministic FakeRealtimeProvider)
- DB head: `0011_stock_screener`
- Room: version 9
- Latest tag: `phase-4-complete`
- GitHub Actions CI: **WAITING FOR CI**

## Phase 5 / Slice 1 Completed Features

- `RealtimeMarketDataProvider` interface with `ProviderCapabilities` and license boundaries
- Deterministic `FakeRealtimeProvider` & `UnconfiguredRealtimeProvider`
- Domain model `RealtimeQuote` using Decimal for prices/amounts & ISO UTC timestamps
- Redis Realtime Cache with TTL, out-of-order rejection, and Pub/Sub channel (`realtime:quotes`)
- WebSocket Hub (`RealtimeQuoteHub`) with subscription limits (100/conn), snapshot delivery, & 100ms coalescing backpressure
- HTTP snapshot endpoints (`GET /v1/quotes/{market}/{code}`, `POST /v1/quotes/batch`, `GET /v1/quotes/health`)
- Android `RealtimeQuoteClient` with OkHttp WebSocket & exponential backoff reconnect
- Android `RealtimeSubscriptionManager` with reference counting
- Android `SecurityDetailScreen` integration with LIVE price badge and real-time streaming updates

## External and Future

- FCM remote push: `UNCONFIGURED`

## Next

Phase 5 / Slice 2 — Intraday Quote + 1m/5m K-line aggregation

Do not start Slice 2 without explicit request.

## Primary References

- `docs/18_PHASE_5_REALTIME_FOUNDATION.md`
- `docs/17_PHASE_4_STOCK_COMPARISON.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
