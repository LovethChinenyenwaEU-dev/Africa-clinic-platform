# How the build matches the product brief

Checked on 15 Oct 2026, at the end of Week 7, against [product-brief.md](./product-brief.md).
Every "built" item was confirmed in the code or tests; every "missing" item was searched for
in the repository. Update this file when a gap is closed or a decision changes.

**Legend:** ✅ built and tested · 🟡 partly built · ⬜ not built yet (planned week shown) · ⚠️ differs from the brief, decision needed

## 1. Where the build differs from the brief

| # | Brief says | What we built | Recommendation |
|---|---|---|---|
| D1 | Backend: "modular TypeScript service (or Go equivalent)" | ✅ **Decided 15 Oct 2026: keep Python + FastAPI**, recorded in [ADR-0004](./adr/0004-python-backend.md). The modular design matches (ADR-0001). | Done. |
| D2 | "PostgreSQL with tenant and **row-level** isolation" (SRS §5.3 says the same) | ✅ Two walls since W11: every query filters by clinic in code (`tenant_select`), **and** PostgreSQL row-level security: signed-in requests run as the role `clinic_app` with `app.tenant_id` set, and a `tenant_wall` policy on every table with a tenant_id shows and accepts only that clinic's rows (`app/core/tenant_wall.py`, migration 0032). Outside the wall on purpose: `staff` (emails unique across clinics) and the audit chain counter. | Done in W11 Step 2. A test fails if a new clinic table lacks the policy. |
| D3 | "**Tamper-evident** audit trail" | ✅ Append-only (a trigger refuses changes and deletes, ADR-0003) **and** tamper-evident since W11: each clinic's lines form a SHA-256 hash chain written by a database trigger; `GET /audit/chain` finds the first changed, removed or inserted line and gives the head (number and hash) to write down. | Done in W11 Step 1. Anchoring the head outside the database (daily export) comes with W12 backups. |

## 2. MVP scope, line by line

### Clinic administration
| Item | Status | Where / plan |
|---|---|---|
| Multi-tenant clinics, branches | ✅ | `tenancy`, clinic-wall tests |
| Users and roles (admin, front desk, nurse, doctor, billing) | ✅ | `identity`, one permission table |
| Services and prices | ✅ | W10 Step 1: `billing/prices.py`, price list in kobo, admin-only changes, every change in the audit log |
| Clinician schedules / availability | ✅ | W9: weekly hours per clinician (in person or remote), free slots; patients may only book a free slot |
| Departments, escalation rules (onboarding) | 🟡 | Escalation built in W9 (12 danger signs: emergency on the queue, in-person care for remote visits). Departments and clinic-configurable rules not built |
| Patient registration, duplicate warnings | ✅ | Deterministic matching, human confirmation, never auto-merged |
| Consent capture | ✅ | Versioned clinic wording, patient or caregiver, withdraw keeps history |
| Audit log | ✅ | Append-only, reads logged, entity + staff/date filters, admin screen |
| Admin **screens** for staff, branches and consent wording | ⬜ | The API exists; admins have no screens for these yet. **Add to W11** (or earlier if a pilot needs them) |

### Appointments and queue
| Item | Status | Where / plan |
|---|---|---|
| Front-desk booking, walk-ins, check-in, cancel, no-show | ✅ | Queue screen, confirmed final actions, Lagos-day list |
| Rescheduling | 🟡 | Backend done and tested; **no button on the screen yet** |
| Triage | ✅ | W9: urgency and danger signs set by a clinician; the queue orders by urgency; front desk sees urgency, not the signs |
| Reminders with retries, one SMS/WhatsApp provider | 🟡 | Queue, worker, retries, consent check all done; **real provider not plugged in** (fake/none only) |
| Admin notification console | ⬜ | No screen showing sent/failed reminders yet. **Add to W11** |
| No-show tracking | 🟡 | Marking ✅; the no-show **rate report** is planned for the W11 dashboards |
| Online / phone booking by patients | 🟡 | W9: patients book free **remote** slots on their own page. In-person online booking and self-cancel not yet |

### Core longitudinal record
| Item | Status | Where / plan |
|---|---|---|
| Demographics, encounters, vitals, problems/diagnoses, allergies, notes | ✅ | Versioned corrections, never overwritten (FR-R3) |
| Attachments | ⬜ | W11 (needs object storage) |
| Prescriptions | ✅ | W9: doctors only, versioned, offline-ready; printed on the referral letter |
| Clinician-approved patient summary | ✅ | W9: drafted from the visit, approved by the encounter owner after sign-off, frozen; the patient reads it on their own page |
| Offline draft/outbox sync | ✅ | W8: device outbox, sent in order with idempotency keys; conflicts kept and settled by a clinician; late entries accepted and marked; offline registration with duplicate review |

### Teleconsult, billing, interoperability, operations
| Item | Status | Plan |
|---|---|---|
| Teleconsult (availability, intake, consent, chat, video, audio/text fallback, note, follow-up, referral) | ✅ | W9: all parts, with Jitsi behind a video adapter (self-hosted Jitsi recommended before going live) |
| Billing (invoice, receipt, refunds, reconciliation, gateway + cash/transfer) | ✅ | W10: `billing/` (prices, invoices, payments, refunds, online, takings); screens under `/billing` |
| FHIR-aligned export | ⬜ | W11. Names already follow FHIR where possible (Encounter, `entered_in_error`, problem-list vs encounter-diagnosis, ICD-10 codes) |
| Retention settings, backup/restore, privacy/incident runbook | ⬜ | W11–W12 |
| Dashboards (wait time, no-shows, completion, sync failures, revenue, record access) | ⬜ | W11 |

## 3. Architecture and security items

| Brief item | Status | Notes |
|---|---|---|
| Next.js staff web app | ✅ | Next.js 16, Tailwind 4; token kept in an httpOnly cookie behind a server pass-through |
| PWA with IndexedDB outbox | ✅ | W8: IndexedDB outbox and minimal offline reads (wiped at sign-out and after 24h), service worker for offline opening. No install manifest yet |
| Background jobs, queue-backed notifications | ✅ | Worker + reminder table as the queue, Redis heartbeat |
| Idempotency keys | ✅ | Device-made IDs on every create, plus the `Idempotency-Key` header with stored responses for every write (W8) |
| Adapters behind retryable interfaces | ✅ | SMS adapter with fake/none; video, payments, labs follow the same pattern later |
| Short-lived tokens | ✅ | 30 minutes; a switched-off staff member is refused on their very next request |
| MFA for privileged staff | ✅ | W11 Step 3: admins and billing sign in with an authenticator app (TOTP, RFC 6238, no new library): set-up screen with the key, 10 one-time backup codes shown once, no code twice, 15-minute lock after 5 wrong codes, admin reset for a lost phone (never one's own). The challenge between password and code stays in an httpOnly cookie. The secret is stored as text until the W12 key manager. |
| Device/session revocation | 🟡 | Switching a person off cuts all their sessions at once; revoking **one device** is not built. W8 records the device on every audit line; revoking one device in **W11** |
| Least-privilege RBAC | ✅ | Plus record-level rules (only the opener signs off, only the author amends) |
| ABAC | ⬜ | Not planned for the MVP; the record-level rules cover today's needs |
| Consent and purpose tracking | 🟡 | Consent purposes ✅. Audit lines have a `purpose` field, but staff are not asked "why" when opening a record |
| Rate limits, circuit breakers | ⬜ | W11 |
| PHI-minimised logs | ✅ | Logs carry IDs and counts only; tested where it matters (reminders, origin check) |
| Structured logs, metrics, tracing, alerting | ⬜ | W11 |
| Encryption at rest, KMS, secrets manager, IaC, staging/prod, canary, SBOM | ⬜ | W12 deployment |
| Clinical safety: no autonomous diagnosis | ✅ | No AI anywhere; vitals ranges catch typing slips only, never judge |

## 4. Gaps that were not on the roadmap

**Update 15 Oct 2026:** items 1–3 were added to the README roadmap (W9, W10, W11) as recommended.

1. **Patient web experience.** The brief and the MVP need patients to book online, do pre-consult intake, see a clinician-approved summary, and download or grant access to records. The roadmap has no week for it. **Recommendation:** build it in W9 together with teleconsult (intake and the summary need it), keeping it lightweight as the brief says.
2. **Services, prices, schedules and triage** (see §2). **Recommendation:** schedules and triage in W9, services and prices in W10.
3. **Admin screens and the notification console** (see §2). **Recommendation:** W11.
4. **Orders, results, care plans** (DiagnosticReport, CarePlan in the brief's FHIR list). They are in the brief's workflows but not its MVP list; lab result import is a PRD "Could have". **Recommendation:** after the MVP.

## 5. Verdict

The build is **in line with the brief's intent and safety rules**: offline-first groundwork,
consent-aware, versioned clinical history, append-only audit, least privilege, clinic isolation,
adapters for external services, no AI. Weeks 1–7 match their roadmap items.

Three points differ from the brief (D1 language, D2 database-level isolation, D3 tamper-evidence)
and four groups of MVP items were missing from the roadmap (§4). None blocks Week 8.
On 15 Oct 2026 D1 was decided (ADR-0004) and §4 items 1–3 were added to the roadmap;
D2 and D3 are scheduled for the W11 security pass.
