# Phase 6 / Slice 1 — Account / Cloud Sync Foundation

## Scope

This slice adds the account, authentication, device, and synchronization foundation and proves it with Watchlist groups/items only. Portfolio, alerts, screeners, settings, import/export, biometrics, widgets, AI, billing, FCM, and production realtime integration remain out of scope.

## Authentication and security

- User IDs are client-visible UUIDs; normalized login identifiers are unique and accounts are `ACTIVE` or `DISABLED`.
- Passwords use maintained Argon2id hashing. The centralized policy accepts 10–256 characters without composition rules. Plaintext passwords are never persisted.
- Access JWTs are short-lived (15 minutes) and contain `sub`, `sid`, `jti`, `iat`, and `exp`. Refresh tokens are high-entropy random values, stored server-side only as SHA-256 hashes, rotated on use, and revocable on logout.
- The auth secret is configuration-owned. Production refuses startup without one; development creates an ephemeral process secret. Production plaintext HTTP is unsupported and TLS must terminate ahead of the API.
- Auth and sync errors use stable error codes (`UNAUTHENTICATED`, `FORBIDDEN`, `SYNC_CONFLICT`, `VALIDATION_ERROR`). Login/register rate limiting is a production ingress/API-gateway requirement because this repository has no shared rate-limit abstraction.

## User and device isolation

Authenticated identity comes only from the bearer token dependency; request bodies cannot choose a user. Every device, operation, change-log, bootstrap, and Watchlist query is scoped server-side by that user. A device is accepted only when its server UUID belongs to the authenticated user and is not revoked.

Android generates and securely retains a random stable `device_public_id`; it does not use IMEI, serial, or MAC address. Server registration is an upsert on `(user_id, device_public_id)`, supporting Device A and Device B without duplicate rows.

## Sync protocol

- Client-created objects and idempotency operations use stable UUIDs.
- Push accepts at most 100 operations and records every operation ID. A retry returns `DUPLICATE` without repeating the mutation.
- Accepted mutations increment the object version and append a user-scoped monotonic change cursor. A stale `base_version` returns the current server version/value as `CONFLICT`; no silent last-write-wins is used.
- Deletes become tombstones. A later stale upsert conflicts instead of resurrecting the object.
- Pull pages are bounded (configured default 100, API maximum 500), indexed by user/cursor, and return `next_cursor`/`has_more`. Bootstrap returns only the current Watchlist snapshot plus a boundary cursor when history is compacted or a device is new.
- Server data is authoritative. Synchronized Watchlist data includes group name/order and item order/note/target/stop/add prices; market price, technical, institutional, and credit snapshots are excluded.

## Android offline model

Room v11 adds per-user cloud Watchlist caches, server version/tombstone/sync state, a durable operation outbox, and a per-user cursor. `CloudSyncManager` pushes pending work, handles accepted/duplicate/conflict/error results, pulls bounded pages, applies each page transactionally, and advances its cursor. It supports foreground/manual synchronization; WorkManager was not introduced because the project has no existing WorkManager foundation.

Tokens and user/device session metadata use Android Keystore-backed AES/GCM storage. The existing Retrofit stack now has bearer injection and a synchronized single-flight refresh authenticator with one retry. Refresh failure clears the session. Login/register/logout/session-expired UX is available from Account. Logout revokes refresh best-effort, clears secrets/current identity, and deletes that user's personal Room cache/outbox/cursor so a subsequent account cannot see it.

UI sync states are `SYNCED`, `PENDING`, `CONFLICT`, and `ERROR`; normal synced state stays quiet while conflicts and retryable work remain explicit. The outbox survives process death and preserves offline mutations.

## Legacy data policy

Migration 0013 leaves pre-existing Watchlist rows unowned. Cloud users never see them. An operator may explicitly run:

```bash
python -m app.cli.claim_legacy_personal_data --user <user-uuid>
```

The command only claims currently unowned rows; there is no public claim endpoint and registration never auto-claims legacy data.

## Validation and limitations

- Targeted auth/device/sync and existing Watchlist regression cover hashing, token expiry/rotation/reuse/logout, disabled users, device upsert, user isolation, idempotency, optimistic conflicts, tombstones, and bounded cursor behavior.
- Deterministic Device A/B semantics are server-driven: A create → B pull; B item create → A pull; competing stale note update → conflict.
- PostgreSQL migration is `0012 → 0013 → 0012 → 0013`; Room migration is explicit `10 → 11`, with no destructive fallback.
- Production realtime provider and FCM remain `UNCONFIGURED` and do not block this slice.
- Background scheduling, conflict-resolution polish, device revocation UI, and other personal domains remain future slices.

## Performance

Local PostgreSQL/API smoke produced 1,000 Watchlist change-log entries in 2.951 s. Pulling the final 100 changes incrementally took 9.97 ms and returned exactly one bounded 100-row page without a bootstrap/full snapshot.
