# 18 — Phase 5 / Slice 1: Realtime Data Provider + WebSocket Foundation

狀態：**COMPLETE**

## Overview

Phase 5 Slice 1 establishes the real-time quote streaming architecture, provider boundaries, Redis caching, multi-worker WebSocket hub, and Android streaming infrastructure.

## Provider Capabilities & License Boundaries

Realtime market data features strictly enforce provider capabilities and legal boundaries (`ProviderCapabilities`):
- `provider_name`: Provider identifier
- `source_type`: Data ingestion type (`WEBSOCKET`, `POLLING`, `FAKE_SIMULATOR`)
- `license_status`: `AUTHORIZED`, `UNVERIFIED`, `NOT_AUTHORIZED`, or `UNCONFIGURED`
- `realtime_available`: Boolean flag
- `delay_seconds`: Ingestion delay
- `redistribution_allowed`: Redistribution rights flag

Quotes are only tagged `LIVE` when `license_status == AUTHORIZED`, `configured == true`, and `realtime_available == true`.

## Quote Domain Model (`RealtimeQuote`)

- Prices and monetary amounts strictly use `Decimal` (no floating-point values).
- Preserves explicit provider timestamps: `exchange_timestamp` vs `received_at`.
- Supports trading sessions (`REGULAR`, `AFTER_HOURS`, `UNKNOWN`) and data statuses (`LIVE`, `STALE`, `DELAYED`, `UNAVAILABLE`).
- Deterministic ordering using sequence numbers and exchange timestamps.

## Redis Realtime Cache & Pub/Sub

- **Cache Key Format**: `realtime:quote:{MARKET}:{CODE}` with TTL (default 120 seconds).
- **Out-of-Order Rejection**: Incoming quotes older than cached quotes (by sequence or timestamp) are rejected.
- **Multi-Worker Fanout**: Normalized quotes published to Redis Pub/Sub channel `realtime:quotes` for multi-worker WebSocket hub distribution.

## WebSocket Protocol v1 (`/v1/ws/quotes`)

- **JSON Payload Format**: `{"type": "subscribe|unsubscribe|ping|pong|status|quote|snapshot|error", "version": 1, ...}`
- **Snapshot Delivery**: Initial cached quote snapshot delivered immediately upon subscription.
- **Subscription Limits**: Maximum 100 securities per WebSocket connection.
- **Backpressure & Coalescing**: 100ms coalescing dispatch loop flushes pending quote updates per client without queuing duplicate updates for the same security.

## HTTP Snapshot APIs

- `GET /v1/quotes/{market}/{code}`: Fetches latest cached realtime quote.
- `POST /v1/quotes/batch`: Fetches batch cached realtime quotes (max 100).
- `GET /v1/quotes/health`: Realtime provider capabilities and pipeline health observation.

## Android Architecture

- **`RealtimeQuoteClient`**: OkHttp WebSocket client in `:core-network` with exponential backoff reconnect and StateFlow updates.
- **`RealtimeSubscriptionManager`**: App-level subscription manager with reference counting for shared connections across screens.
- **`SecurityDetailScreen`**: Integrates `LIVE` price badge and realtime update display.

## Test Coverage

- **Backend Unit Tests**: `tests/test_realtime.py` (Provider capabilities, Redis cache ordering, Hub subscription limits, HTTP snapshot APIs).
- **Android Unit Tests**: `core-network/src/test/.../RealtimeNetworkTest.kt` (Subscription reference counting, domain models).
