# Phase 6 / Slice 5 — AI Grounded Analysis + Production Integration Hardening

狀態：**IN PROGRESS** (Awaiting GitHub CI)

## 1. AI Grounded Analysis Architecture

### Grounding Package
- Deterministic facts synthesized exclusively by server-side `GroundingBuilder` from canonical database models.
- Typed `GroundingFact` entries with explicit `category`, `key`, `value`, `data_status`, and `as_of`.
- Strictly bounded context (no raw DB dumps, no arbitrary SQL generation, no raw token/password leakage).

### AI Analysis Types
1. **`MARKET_SUMMARY`**: TAIEX/TPEx index level, daily breadth, institutional net flows.
2. **`SECURITY_SUMMARY`**: OHLC, MA20, RSI14, 5-day foreign flow, active market status.
3. **`PORTFOLIO_SUMMARY`**: Positions, average cost, cost basis, asset allocation (strictly read-only; requires explicit user opt-in).
4. **`INDUSTRY_SUMMARY`**: Industry theme strength score, ranking, member summary.
5. **`COMPARISON_SUMMARY`**: Multi-stock performance spread and comparison metrics.
6. **`SCREENER_SUMMARY`**: Screener expression criteria interpretation and match count.

### Structured Response Schema
Every analysis returns structured statements explicitly categorized:
- `[FACT]` (客觀事實): Canonical values directly from TWML deterministic calculations.
- `[INFERENCE]` (分析推論): Structural interpretations of observed facts.
- `[CAVEAT]` (資料限制): Missing/stale field warnings and delayed data notifications.
- `risks`: Potential market risks associated with the grounding package.

### Privacy & Consent Boundary
- **Personal Portfolio AI**: `UserSettingsModel.allow_ai_portfolio_analysis` is **OFF by default**.
- Requests to analyze portfolio without consent fail with `AI_PORTFOLIO_CONSENT_REQUIRED` (HTTP 403).
- Opt-in consent dialog explicitly outlines that no passwords, session tokens, or device IDs are transmitted.

### Provider Abstraction & Caching
- `AIAnalysisProvider` interface:
  - `UnconfiguredAIProvider`: Default production provider when external credentials are absent.
  - `FakeAIProvider`: Deterministic offline synthesizer for DEV/TEST/CI.
- Caching: SHA-256 grounding fingerprint + prompt version + user scope cached in Redis with a 1-hour TTL.

---

## 2. Production Integration Hardening

### Realtime Production Gate
- Multi-predicate production gate:
  - `configured == true`
  - `realtime_available == true`
  - `license_status == AUTHORIZED`
  - `redistribution_allowed == true`
- If any predicate fails, status defaults to `UNCONFIGURED`, `UNAUTHORIZED`, `DELAYED`, or `UNAUTHORIZED_REDISTRIBUTION`, never `LIVE`.

### FCM / Push Notification Lifecycle
- `PushNotificationProvider` interface with `UnconfiguredPushProvider` and `FakePushProvider`.
- Device token lifecycle: `register_token` associates token with authenticated user device; `unregister_token` decouples token upon user logout.
- Alert deduplication: Redis/local event deduplication prevents duplicate push alerts.
- Minimal push payload: only contains `event_id`, `alert_type`, `security_code`, `title`, and `body` (no financial values or secrets).

### Operational Health & Readiness
- `/v1/ready` reports component readiness across:
  - Database (`UP` / `DOWN`)
  - Redis (`UP` / `UNAVAILABLE`)
  - AI Provider (`READY` / `UNCONFIGURED`)
  - Push Provider (`READY` / `UNCONFIGURED`)
  - Realtime Provider Gate (`LIVE` / `DELAYED` / `UNCONFIGURED` / `UNAUTHORIZED`)
- Secrets (tokens, API keys, credentials) are strictly redacted from health responses and log messages.

---

## 3. Database & Room

- **PostgreSQL Head**: `0014_personal_data_sync` (No migration required; uses existing `UserSettingsModel` and `UserDeviceModel`).
- **Room DB Version**: `v12` (No Android database schema changes).

---

## 4. Production Capabilities Status

- **AI Provider**: `UNCONFIGURED` (Production default; `FakeAIProvider` used in test/dev).
- **Production Realtime Provider**: `UNCONFIGURED` (Requires authorized licensed feed).
- **FCM**: `UNCONFIGURED` (Requires production Firebase project credentials).
