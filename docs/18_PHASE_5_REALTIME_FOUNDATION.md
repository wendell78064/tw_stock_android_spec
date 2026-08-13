# 18 — Phase 5 / Slice 1: Realtime Data Provider + WebSocket Foundation

狀態：**COMPLETE** (Software Foundation)

> **Production Realtime Provider**: `UNCONFIGURED`  
> Phase 5 / Slice 1 software foundation is **COMPLETE**. However, Phase 5 as a whole cannot be marked **COMPLETE** until an official, authorized production real-time provider is configured and validated.

## Overview

Phase 5 Slice 1 establishes the real-time quote streaming architecture, provider capabilities boundary, Redis caching, multi-worker WebSocket hub, and Android streaming infrastructure.

## Provider Capabilities & License Boundaries

Realtime market data features strictly enforce provider capabilities and legal boundaries (`ProviderCapabilities`):
- `provider_name`: Provider identifier (`RealtimeMarketDataProvider` interface)
- `source_type`: Data ingestion type (`WEBSOCKET`, `POLLING`, `FAKE_SIMULATOR`)
- `license_status`: `AUTHORIZED`, `UNVERIFIED`, `NOT_AUTHORIZED`, or `UNCONFIGURED`
- `realtime_available`: Boolean flag
- `delay_seconds`: Ingestion delay
- `redistribution_allowed`: Redistribution rights flag

Quotes are tagged `LIVE` **only** when `license_status == AUTHORIZED`, `configured == true`, and `realtime_available == true`.
Otherwise, quotes are tagged `DELAYED`, `STALE`, or `UNAVAILABLE`.

## Implemented Components

- **`RealtimeMarketDataProvider`**: Abstract interface for real-time market data ingestion.
- **`FakeRealtimeProvider`**: Deterministic simulator for testing, CI, and local development.
- **`UnconfiguredRealtimeProvider`**: Safe placeholder when production credentials are absent.

## Quote Domain Model (`RealtimeQuote`)

- All prices and monetary amounts strictly use `Decimal` (no floating-point types).
- Explicit timestamp separation: `exchange_timestamp` (exchange event time) vs `received_at` (system ingestion time).
- Supports trading sessions (`REGULAR`, `AFTER_HOURS`, `UNKNOWN`) and data statuses (`LIVE`, `STALE`, `DELAYED`, `UNAVAILABLE`).
- Deterministic ordering using sequence numbers and exchange timestamps.

## Redis Realtime Cache & Pub/Sub

- **Cache Key Format**: `realtime:quote:{MARKET}:{CODE}` with TTL (default 120 seconds).
- **Out-of-Order Rejection**: Incoming quotes older than cached quotes (by sequence or timestamp) are rejected.
- **Multi-Worker Fanout**: Normalized quotes published to Redis Pub/Sub channel `realtime:quotes` for multi-worker WebSocket hub distribution.

## WebSocket Protocol v1 (`/v1/ws/quotes`)

- **JSON Protocol**: `{"type": "subscribe|unsubscribe|ping|pong|status|quote|snapshot|error", "version": 1, ...}`
- **Snapshot Delivery**: Initial cached quote snapshot delivered immediately upon subscription.
- **Subscription Limits**: Maximum 100 securities per WebSocket connection.
- **Backpressure & Coalescing**: 100ms coalescing dispatch loop flushes pending quote updates per client without queuing duplicate updates for the same security.
- **Heartbeat & Reconnect**: Client/server ping-pong heartbeat and exponential backoff reconnect with jitter.

## HTTP Snapshot APIs

- `GET /v1/quotes/{market}/{code}`: Fetches latest cached realtime quote.
- `POST /v1/quotes/batch`: Fetches batch cached realtime quotes (max 100).
- `GET /v1/quotes/health`: Realtime provider capabilities and pipeline health observation.

## Android Architecture

- **`RealtimeQuoteClient`**: OkHttp WebSocket client in `:core-network` with exponential backoff reconnect and StateFlow updates.
- **`RealtimeSubscriptionManager`**: App-level subscription manager with reference counting for shared connections across screens.
- **`SecurityDetailScreen`**: Integrates `LIVE` price badge and realtime update display.

## Test Coverage & CI Validation

GitHub Actions Run: **31670900266**

| Job | Result |
|-----|--------|
| backend | PASS |
| android | PASS |
| android-instrumentation | PASS |

- **Backend Unit Tests**: `tests/test_realtime.py` (Provider capabilities, Redis cache ordering, Hub subscription limits, HTTP snapshot APIs).
- **Android Unit Tests**: `core-network/src/test/.../RealtimeNetworkTest.kt` (Subscription reference counting, domain models).
