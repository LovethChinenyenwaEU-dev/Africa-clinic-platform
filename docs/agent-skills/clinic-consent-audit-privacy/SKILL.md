---
name: clinic-consent-audit-privacy
description: Rules for consent capture, append-only audit logging, PHI-safe logging and privacy handling in the Clinic Platform. Use whenever code reads, writes, exports, shares or logs patient data, when building consent screens, referrals, patient summaries, access history, data retention or deletion, error handling or observability, and whenever the user mentions privacy, consent, audit, NDPA, PHI, logs, or who accessed a record.
---

# Consent, audit and privacy

This project is designed to support Nigerian data-protection obligations (Nigeria Data Protection Act 2023) and professional confidentiality expectations. Do not claim compliance; say the design supports it pending professional review.

## Consent
- Store consent as records: `{ patient_id, purpose, text_version, granted_by (patient or proxy), granted_at, revoked_at }`.
- Consent text is clinic-configurable and versioned; always store which version was shown.
- Check consent before sharing a summary with another clinic and before teleconsult recording or attachment sharing.
- Revocation takes effect for future access and is itself audited.
- Proxy/caregiver access records the authority relationship.

## Audit log (append-only)
- One event for every PHI **read, create, update, export, share, and resolve-conflict** action.
- Fields: `id, tenant_id, actor_id, patient_id, action, entity, entity_id, purpose, device/session, ip (if appropriate), at`.
- Append-only: no update or delete routes; database role used by the app has insert/select only on this table.
- Write the audit event in the **same transaction** as the action, so an action cannot succeed without its audit record.
- Provide admin views to filter by patient, staff and date.
- Break-glass or support access must be explicit, time-limited and audited.

## Logging and observability
- Logs, traces and error reports must **not** contain names, phone numbers, diagnoses, note text or tokens. Log IDs and event types only.
- Scrub request bodies in error handlers. Mask identifiers in analytics.
- Test with a fixture that scans captured logs for fake PHI strings.

## Data handling
- Encrypt in transit and at rest; secrets in a secrets manager.
- Minimise what endpoints return; do not expose more fields than a role needs.
- Retention and deletion are configurable per tenant; deletion of clinical data goes through a reviewed workflow, never ad hoc scripts.
- Never sell or share identifiable patient data. De-identified analytics only with explicit governance and customer opt-in; out of MVP scope.
- Use clearly fake data in development, tests and demos.

## Safe-failure behaviour
If consent is missing or ambiguous, deny and explain what is needed. If audit writing fails, the action fails.

## Tests required
- Viewing a record creates exactly one audit event
- Sharing without valid consent is rejected
- Revoked consent blocks new shares
- Audit table rejects update/delete from the app role
- Log capture contains no fake PHI after exercising endpoints
