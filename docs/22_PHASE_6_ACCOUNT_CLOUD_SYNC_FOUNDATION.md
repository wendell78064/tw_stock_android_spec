# Phase 6 / Slice 1 — Account / Cloud Sync Foundation

狀態：**COMPLETE**

## Overview

Phase 6 Slice 1 adds the account, authentication, multi-device identity, and transactional cloud synchronization foundation, validated with Watchlist multi-device sync.

## Authentication and Security

- **User Accounts**: User IDs are client-visible UUIDs; normalized login identifiers are unique and accounts are `ACTIVE` or `DISABLED`.
- **Password Hashing**: Passwords use maintained Argon2id hashing. Centralized policy accepts 10–256 characters without arbitrary composition rules. Plaintext passwords are never persisted.
- **Token Management**: Access JWTs are short-lived (15 minutes) containing `sub`, `sid`, `jti`, `iat`, and `exp`. Refresh tokens are high-entropy random values, stored server-side only as SHA-256 hashes, rotated on use, and revocable on logout.
- **Security Boundaries**: Production requires a configured auth secret and HTTPS/TLS termination ahead of the API. Plaintext HTTP in production is rejected.
- **Error Conventions**: Auth and sync errors use stable error codes (`UNAUTHENTICATED`, `FORBIDDEN`, `SYNC_CONFLICT`, `VALIDATION_ERROR`).

## User and Device Isolation

- **Server-Side Identity**: Authenticated identity is derived strictly from bearer tokens; request payloads cannot specify a target user.
- **Device Identity**: Android generates and securely retains a random stable `device_public_id` (no IMEI/MAC/serial). Server registration is an upsert on `(user_id, device_public_id)`, supporting multi-device setups without duplicate rows.

## Sync Protocol & Conflict Handling

- **Idempotency**: Operation IDs use client-generated UUIDs. Server push accepts up to 100 operations per request and returns `DUPLICATE` without repeating mutations on retries.
- **Optimistic Concurrency**: Accepted mutations increment object version and append a user-scoped monotonic change cursor. Stale `base_version` requests return `CONFLICT` with server values (no silent last-write-wins).
- **Tombstones**: Deletes persist as tombstones to prevent resurrecting deleted items upon stale upserts.
- **Cursor Pagination & Snapshots**: Pulls are bounded (default 100, max 500) with `next_cursor` and `has_more`. Bootstrapping returns Watchlist snapshots plus boundary cursors for new devices or compacted logs.
- **Canonical Boundary**: Synchronized Watchlist data includes group name/order and item order/note/target/stop/add prices. Market price, technical, institutional, and credit snapshots are excluded.

## Android Infrastructure & Offline Model

- **Room v11**: Per-user cloud Watchlist caches, server version/tombstone/sync state, durable outbox, and per-user cursors.
- **Keystore Security**: Tokens and user/device session metadata use Android Keystore-backed AES/GCM storage.
- **Network Pipeline**: Retrofit stack features bearer injection and a synchronized single-flight refresh authenticator. Refresh failure revokes session.
- **`CloudSyncManager`**: Pushes outbox operations, handles `SYNCED`, `PENDING`, `CONFLICT`, and `ERROR` UI states, and processes pull pages transactionally.
- **Session Cleanup**: Logout revokes refresh tokens best-effort, clears identity, and purges personal Room caches, outbox, and cursors.

## Legacy Data Policy

- Alembic Migration `0013_account_sync_foundation` leaves pre-existing Watchlist rows unowned.
- Unowned rows are hidden from cloud users. Operators can claim legacy data via explicit CLI command (`python -m app.cli.claim_legacy_personal_data --user <user-uuid>`). No public API claim endpoint exists.

## Performance Metrics

- **1,000 Changes Benchmark**: 2.951 s
- **Incremental 100-Change Pull**: 9.97 ms
- **Bounded Page Size**: 100 rows

## Test Coverage & CI Validation

GitHub Actions Run: **31688347536**

| Job | Result |
|-----|--------|
| backend | PASS |
| android | PASS |
| android-instrumentation | PASS |

- **API Level**: 35 (`google_apis`, `x86_64` emulator)
- **Local Device Execution**: NOT RUN
- **Room v10 → v11 Migration Runtime Execution**: NOT RUN
