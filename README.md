# Africa-first Clinic Platform
![CI](https://github.com/LovethChinenyenwaEU-dev/Africa-clinic-platform/actions/workflows/ci.yml/badge.svg)

> An offline-first clinic management, telemedicine, and patient-record system built for Nigerian clinics, designed to keep working when the internet and power don't.

![status](https://img.shields.io/badge/status-in%20development-orange) ![stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Next.js%20%7C%20PostgreSQL-blue)

**Live demo:** `[add link]` | **Demo video:** `[add link]` | **Docs:** [Brief](./docs/product-brief.md) · [PRD](./docs/PRD.md) · [SRS](./docs/SRS.md) · [Decisions](./docs/adr) · [Build log](./LOG.md)

> **Important:** this is a portfolio and research project. It has not been through clinical-safety review, a privacy impact assessment, or legal review, and it must not be used with real patient data until those are done.

---

## The problem

Private clinics in Nigeria often run on separate tools for booking, video calls, billing, and patient files. Unreliable internet and power break each of them, records don't follow the patient between clinics, and handling patient data without clear consent is a legal and trust risk.

## The solution

One system that covers the clinic's whole day and keeps working offline:

- **Front desk:** registration with duplicate warnings, appointments, walk-in queue, SMS/WhatsApp reminders, no-show tracking
- **Clinical:** encounters, vitals, allergies, notes, prescriptions, and a clinician-approved patient summary
- **Telemedicine:** pre-consult intake, consent, chat, video with audio/text fallback, follow-up, and referral
- **Money:** invoices, receipts, refunds, daily reconciliation, one payment gateway plus manual cash/transfer
- **Trust:** consent tracking, role-based access, and an append-only audit log of who viewed what
- **Portability:** FHIR-aligned export so records can move between providers

## Key design decisions

| Decision | Why |
|---|---|
| **Offline-first PWA** with an IndexedDB outbox | Clinics lose connectivity; clinical writes must never be silently discarded |
| **Idempotency keys** on every write | A retried sync must never create duplicates |
| **Keep-both conflict rule** | Clinical history is preserved, never overwritten; a clinician resolves clashes |
| **Multi-tenant with row-level isolation** | One clinic can never read another's data |
| **Adapters for SMS, payments, video** | Swap a provider by replacing one adapter, not the system |
| **FHIR-aligned data model** | Open standard for exchanging health data with labs, pharmacies, and insurers |
| **No AI in the MVP** | Get the basics reliable and safe first |

## Architecture

```mermaid
flowchart TD
  U[Staff, doctors, patients] --> W[Web app / PWA<br/>offline outbox]
  W --> API[FastAPI backend<br/>scheduling, records, billing, telehealth, referrals]
  API --> DB[(PostgreSQL)]
  API --> OBJ[(Object storage)]
  API --> Q[[Redis job queue]]
  Q --> EXT[Adapters: SMS/WhatsApp, payments, video, labs/HMOs]
```

## Data model (core)

```mermaid
erDiagram
  TENANT ||--o{ BRANCH : owns
  BRANCH ||--o{ STAFF : employs
  TENANT ||--o{ PATIENT : registers
  PATIENT ||--o{ CONSENT : grants
  PATIENT ||--o{ APPOINTMENT : books
  APPOINTMENT ||--o| ENCOUNTER : leads_to
  ENCOUNTER ||--o{ OBSERVATION : records
  ENCOUNTER ||--o{ PRESCRIPTION : issues
  ENCOUNTER ||--o{ REFERRAL : creates
  ENCOUNTER ||--o| INVOICE : bills
  INVOICE ||--o{ PAYMENT : settled_by
  PATIENT ||--o{ AUDIT_EVENT : accessed_in
```

## How offline sync works

1. A nurse saves a note with no internet. It is stored on the device and added to the **outbox**.
2. The screen shows **pending**, so nothing is silently lost.
3. When connectivity returns, the outbox sends each write with a **unique ID**.
4. The server ignores duplicates, detects conflicts, and records an audit event.
5. If two edits clash, **both versions are kept** and a clinician picks the correct one.
6. The device receives confirmation and shows **synced**.

## Project structure

A modular monolith organised by feature. See [ADR-0001](./docs/adr/0001-modular-monolith.md).

```
backend/app/core/        config, db, events, shared plumbing
backend/app/modules/     one folder per business area (tenancy, identity, patients, ...)
frontend/src/features/   mirrors the backend modules
docs/                    PRD, SRS, decisions, agent skills
```

## Tech stack

- **Frontend:** Next.js, React, Tailwind CSS, PWA with IndexedDB
- **Backend:** Python, FastAPI, SQLModel, Alembic
- **Data:** PostgreSQL, Redis, S3-compatible object storage
- **Tooling:** Docker / Docker Compose, Git & GitHub, Postman or Bruno for API testing, pytest

## Getting started

```bash
git clone https://github.com/LovethChinenyenwaEU-dev/africa-clinic-platform.git
cd africa-clinic-platform
cp .env.example .env
docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs
- Run tests: `docker compose exec api pytest` (backend) and `docker compose exec web npm test` (frontend)
- Reminder worker: starts with the stack as the `worker` service. Watch it with `docker compose logs -f worker`. `SMS_PROVIDER=none` in `.env` means nothing is really sent.

### Try it with demo data (development only)

```bash
docker compose exec api python -m app.cli seed-demo
```

This creates a demo clinic with clearly fake patients and five logins (`admin`, `front_desk`, `nurse`, `doctor`, `billing` at `@demo.example.com`), all with the password you type. It refuses to run unless `ENVIRONMENT` is `development` or `test`. Forgot the password? `python -m app.cli reset-demo-passwords` changes it for the demo logins only.

### Running in GitHub Codespaces

- After the Codespace stops (for example the idle timeout), bring everything back with `docker compose up -d`.
- After a new frontend package is added, refresh the web container's packages: `docker compose up -d --build --renew-anon-volumes web`.

## Roadmap (12-week MVP)

- [x] W1 Foundation: repo, Docker Compose, CI
- [x] W2 Tenants, branches, staff, roles, auth
- [x] W3 Patients: registration, duplicate warning, consent
- [x] W4 Scheduling: appointments, walk-in queue, check-in, no-show
- [x] W5 Reminders via job queue and one SMS/WhatsApp adapter (adapter interface done; real provider still to plug in)
- [x] W6 Encounters, records, audit log (vitals, allergies, problems, versioned notes; attachments, prescriptions and the patient summary moved to W9/W11)
- [x] W7 Staff web app screens (patients and consent, today's queue, encounter record, audit log)
- [x] W8 Offline sync and conflict handling (device outbox with idempotency keys, conflicts kept for a clinician to settle, late entries marked, offline reads wiped at sign-out and after 24h, service worker, offline registration with review; merging duplicate patients moved to W11)
- [x] W9 Teleconsult flow, prescriptions, clinician-approved patient summary, clinician schedules, triage, lightweight patient web experience (prescriptions for doctors; triage with 12 danger signs ordering the queue; weekly hours and free slots; intake with consent and in-person escalation; Jitsi room behind an adapter with video→audio→text and chat; follow-up and referral letter; approved summaries; patient sign-in by SMS code to see visits and summaries, book a remote slot, answer the intake and join the consult. Patient self-cancel and caregiver access later)
- [ ] W10 Billing and one payment gateway, services and prices
- [ ] W11 FHIR export, dashboards, attachments, admin screens and notification console, security pass (database row-level security, tamper-evident audit, MFA, device revocation)
- [ ] W12 Deploy, backup/restore test, demo

Update the checkboxes as you finish each week.

## Security and privacy

- Tenant isolation, least-privilege roles, and short-lived tokens
- Consent and purpose tracking; append-only access logs
- Logs minimise patient data; patient data is never sold
- Designed with the Nigeria Data Protection Act 2023 in mind. This is **not** a compliance certification or legal advice.

## What I learned / hardest problems

- `[Fill in after building: e.g. designing conflict rules that preserve clinical history]`
- `[Fill in: e.g. how I tested tenant isolation]`
- `[Fill in: measured result, e.g. "N of N offline notes synced with zero duplicates"]`

## What's next

Lab-result integration, HMO/insurer APIs, multi-branch groups, and West African adapters (country-specific consent language, payment rails, and telemedicine rules).

## Author

**Loveth Chinenyenwa Edeugwu**: software developer with a background in medical laboratory science (hematology and clinical chemistry).
LinkedIn: [linkedin.com/in/lovethchinenyenwaeu-dev](https://linkedin.com/in/lovethchinenyenwaeu-dev) · GitHub: [LovethChinenyenwaEU-dev](https://github.com/LovethChinenyenwaEU-dev)

## Acknowledgements

Context drawn from WHO workforce estimates, GSMA's Mobile Economy Sub-Saharan Africa 2024, WHO/HL7 interoperability guidance, HL7 FHIR, and the Nigeria Data Protection Commission and MDCN guidance.

## License

`[Choose a license, e.g. MIT, before publishing]`
