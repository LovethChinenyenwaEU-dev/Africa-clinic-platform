---
name: clinic-offline-sync-outbox
description: Design and implementation rules for offline-first behaviour in the Clinic Platform PWA and API, covering the IndexedDB outbox, idempotency keys, sync status, retries and conflict handling. Use whenever building or changing any feature that must work without internet, any create/update endpoint that the frontend may retry, sync code, service workers, or when the user mentions offline, outbox, sync, duplicates, conflicts, flaky network, or "what happens if the connection drops".
---

# Offline-first sync

Principle: **a clinical write is never lost, never duplicated, and never silently overwritten.**

## Flows that must work offline (MVP)
Patient registration, viewing today's appointments, vitals, clinical notes, prescription drafts. Billing, teleconsult video and exports may require a connection.

## Client rules (Next.js PWA)
1. Save to IndexedDB first, then try the network. The UI reads from local state so it never blocks on the network.
2. Each user action creates an outbox entry: `{ id (UUID = idempotency key), entity, entityId, operation, payload, baseVersion, createdAt, attempts, status }`.
3. Statuses: `pending → syncing → synced | failed | conflict`. Show them on each record and in a global indicator.
4. Retry with exponential backoff and jitter; stop and surface `failed` after a limit. Never delete a failed entry.
5. Process the outbox in order per entity so edits apply sequentially.
6. Do not generate server-visible IDs that could collide: use client-generated UUIDs.

## Server rules (FastAPI)
1. Require an `Idempotency-Key` header on mutating endpoints used by sync. Store `(tenant_id, key) → response`. A repeat key returns the stored response and performs no new write.
2. Accept `baseVersion` with updates. If it does not match the current version, **do not overwrite**: store the incoming change as a new version marked `conflict` and return `409` with both versions.
3. Writes and their audit events are in the same transaction.
4. Return enough data for the client to mark the entry synced (new version, server timestamp).

## Conflict policy
Keep both versions. A clinician resolves by choosing, or merging into a new version. Resolution creates a new version and an audit event. Never auto-merge clinical free text.

## Never
- Discard a write because of a network error, timeout, or validation failure without surfacing it
- Use "last write wins" for clinical data
- Clear local data on logout while the outbox is non-empty (warn and block)

## Tests required
- Replay the same request 3 times: exactly one record
- Go offline, save 10 notes, reconnect: all 10 arrive, none duplicated
- Two clients edit the same record offline: two versions preserved and flagged
- Kill the app mid-sync: entries survive and resume
- Server returns 500 repeatedly: entry ends `failed`, remains visible and retryable

## Metrics to expose
Sync lag, failed entries count, conflict count, retry count. These feed the dashboard and the README's "measured result".
