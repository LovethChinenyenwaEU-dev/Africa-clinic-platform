# Product Requirements Document (PRD)

**Product:** Africa-first Clinic Platform (clinic management, telemedicine, longitudinal health record)
**Author:** Loveth Chinenyenwa Edeugwu
**Status:** Draft v0.1
**Market:** Nigeria first; designed for West Africa later

---

## 1. Overview

A multi-tenant, offline-first platform that gives private Nigerian clinics one system for scheduling, patient records, teleconsults, and billing, with a patient-controlled, portable health record.

## 2. Problem statement

Clinics use separate tools for appointments, video, billing, and records. Unreliable connectivity and power make each fragile, records do not follow patients between providers, and consent and privacy handling is inconsistent.

**Context (from the project brief):** WHO projects an 11 million health-worker shortfall by 2030; GSMA reports 27% mobile-internet penetration in Sub-Saharan Africa (end-2023) with a 60% usage gap. Together these support an efficient, low-bandwidth product and argue against assuming always-on video.

**Key assumption to validate:** clinics will pay for operational wins (shorter waits, fewer no-shows). Validate with 10 to 20 clinics before broadening scope.

## 3. Goals and non-goals

**Goals**
1. Let a clinic run a full day (register, book, treat, bill) with or without internet.
2. Never lose or silently overwrite clinical data.
3. Make consent and access auditable.
4. Show measurable operational improvement in a pilot.

**Non-goals (MVP)**
- AI diagnosis or autonomous clinical decisions
- Marketplace of providers
- Native mobile apps
- Insurance claims adjudication
- Selling patient data (never)
- Countries beyond Nigeria

## 4. Users and personas

| Persona | Needs |
|---|---|
| **Clinic owner/admin** | Set up branches, staff, prices; see revenue and no-show reports |
| **Front-desk officer** | Register patients fast, book, manage the queue, take payments |
| **Nurse** | Record vitals and notes, even offline |
| **Doctor** | See history, consult in person or remotely, prescribe, refer |
| **Patient/caregiver** | Book, get reminders, consult remotely, access their records |
| **Partner (lab/HMO/pharmacy)** | Receive referrals and send results through APIs (post-MVP) |

## 5. User stories (MVP)

**Must have**
- As an admin, I configure branches, staff roles, services, and consent text.
- As front desk, I register a patient and am warned about possible duplicates.
- As front desk, I book appointments and manage walk-ins in a queue.
- As a patient, I receive an SMS/WhatsApp reminder.
- As a nurse, I save vitals offline and see a clear pending/synced status.
- As a doctor, I record an encounter with diagnosis, notes, and prescription.
- As a doctor, I run a teleconsult with chat and video, falling back to audio or text on weak signal.
- As front desk, I issue an invoice and record payment (gateway or manual cash/transfer).
- As an admin, I view who accessed which patient record.
- As a patient, I can obtain a clinician-approved summary of my record.

**Should have**
- Patient grants another clinic access to a summary (referral).
- Daily reconciliation report.
- FHIR-aligned export for patient, encounter, observation, medication, consent.

**Could have**
- Caregiver/proxy access
- Lab result import

## 6. Functional requirements (summary)

| ID | Area | Requirement | Priority |
|---|---|---|---|
| P-01 | Tenancy | Branches, staff, roles, services, schedules | Must |
| P-02 | Patients | Registration, duplicate warning, consent capture | Must |
| P-03 | Scheduling | Booking, walk-in queue, triage status, no-show tracking | Must |
| P-04 | Notifications | SMS/WhatsApp reminders with retry | Must |
| P-05 | Records | Encounters, vitals, allergies, problems, notes, attachments, prescriptions | Must |
| P-06 | Offline | Local drafts and outbox sync for high-value flows | Must |
| P-07 | Telemedicine | Availability, intake, consent, chat, video, audio/text fallback, note, follow-up, referral | Must |
| P-08 | Billing | Invoice, receipt, refund, payment status, reconciliation | Must |
| P-09 | Audit | Append-only access and change log | Must |
| P-10 | Interop | FHIR-aligned export | Should |
| P-11 | Reporting | Dashboards: wait time, no-shows, consult completion, sync failures, revenue | Should |
| P-12 | Referral | Patient-approved summary shared with another clinic | Should |

Detailed, testable requirements are in the [SRS](./SRS.md).

## 7. Success metrics

| Metric | Target (to be validated in pilot) |
|---|---|
| Clinics completing onboarding | [N] pilot clinics |
| No-show rate | Reduced vs. clinic baseline |
| Average patient wait time | Reduced vs. clinic baseline |
| Offline sync success | No lost or duplicated writes in testing |
| Teleconsult completion rate | [X]% of started consults |
| Paid conversion and retention | Gate any expansion on these |
| Support cost per clinic | Within pricing assumptions |

Targets are placeholders until baseline data exists from interviews and pilots.

## 8. Business model (summary)

- Per-branch subscription in naira (monthly or annual) with tier limits
- Usage fees: teleconsults, SMS/WhatsApp, storage, premium video, with transparent pass-through of third-party costs
- Enterprise/API contracts for groups, HMOs, labs, pharmacies
- No sale of identifiable patient data; any de-identified analytics needs governance, contracts, and customer opt-in

## 9. MVP scope and timeline

12-week solo plan: foundation, tenancy, patients, scheduling, reminders, records, staff UI, offline sync, teleconsult, billing, FHIR/dashboards/security, then deploy and pilot feedback. **Cut order if behind:** video (keep chat), payment gateway (keep manual), dashboards.

## 10. Assumptions and dependencies

- One SMS/WhatsApp provider, one video provider, one Nigerian payment gateway are available and affordable
- Pilot clinics will share process feedback
- Counsel can interpret licensing and consent requirements
- Managed cloud region acceptable to customers

## 11. Risks

| Risk | Mitigation |
|---|---|
| Unsafe remote care | Protocol limits, red-flag triage, in-person escalation, licensed clinicians only, not marketed as diagnosis |
| Privacy breach | Least privilege, MFA, encryption, tenant isolation, audit, privacy impact assessment |
| Regulatory uncertainty | Counsel, configurable consent and verification, jurisdiction matrix |
| Poor connectivity | Offline-first, retries, visible sync state |
| Duplicate/unsafe merges | Deterministic plus human-reviewed matching, versioning |
| Fraud/payment errors | Idempotent billing, reconciliation, role-separated approval |
| Low adoption | Co-design, import tools, local pricing, gated expansion |

## 12. Open questions

1. Which Nigerian states and clinic types to pilot first?
2. Which licensing or registration steps apply to telemedicine for each clinic type?
3. What do clinics currently pay for SMS, billing, and records tools?
4. Which video and SMS providers give acceptable cost and reliability?
5. What data-residency expectations do clinics have?

## 13. Out of scope for this document

Pricing amounts, legal opinions, and clinical protocols. These need local professionals.
