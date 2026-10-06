# Software Requirements Specification (SRS)

**Product:** Africa-first Clinic Platform
**Version:** 0.1 (draft)
**Author:** Loveth Chinenyenwa Edeugwu
**Related:** [PRD](./PRD.md)

Numeric targets below are **proposed** and must be validated in testing and pilots.

---

## 1. Introduction

### 1.1 Purpose
Defines the testable software requirements for the MVP of a multi-tenant, offline-first clinic management, telemedicine, and health-record platform.

### 1.2 Scope
Staff web app (PWA), lightweight patient web experience, and backend API covering tenancy, patients, scheduling, records, teleconsults, billing, audit, and FHIR-aligned export. Excludes AI features, native apps, insurance adjudication, and non-Nigerian deployments.

### 1.3 Definitions
| Term | Meaning |
|---|---|
| Tenant | A clinic organisation; owns branches, staff, patients |
| Encounter | A single clinical visit (in person or remote) |
| Outbox | Local queue of unsent writes on a device |
| Idempotency key | Unique ID that makes a retried request safe |
| PHI | Personal health information |
| FHIR | HL7 standard for exchanging health data via APIs |
| RPO/RTO | Max tolerable data loss / recovery time |
| NDPA | Nigeria Data Protection Act 2023 |

### 1.4 References
Project brief; HL7 FHIR; NDPA 2023 and NDPC guidance; MDCN guidance on confidentiality and consent for identifiable clinical material online.

## 2. Overall description

### 2.1 Product perspective
Standalone SaaS with adapters to external providers (SMS/WhatsApp, payments, video, later labs/HMOs).

### 2.2 User classes
Admin, front-desk officer, nurse, doctor, patient/caregiver, platform operator.

### 2.3 Operating environment
Modern mobile and desktop browsers on low-end devices and slow networks; containerised services on a managed cloud; PostgreSQL, Redis, object storage.

### 2.4 Constraints
- Intermittent connectivity and power
- Regulatory requirements for consent, privacy, and clinician licensing
- Solo-developer capacity for the MVP

### 2.5 Assumptions and dependencies
Third-party providers are available; clinics supply their own price lists and consent text; counsel reviews regulatory interpretation before any production use.

## 3. Functional requirements

Priority: **M** = must, **S** = should.

### 3.1 Tenancy and access
| ID | Requirement | P |
|---|---|---|
| FR-T1 | The system shall support tenants with multiple branches. | M |
| FR-T2 | The system shall provide roles (admin, front-desk, nurse, doctor, billing) with least-privilege permissions. | M |
| FR-T3 | Every data query shall be scoped by tenant; a user shall never read another tenant's data. | M |
| FR-T4 | Privileged roles shall require MFA. | S |
| FR-T5 | Admins shall be able to revoke a user's sessions and devices. | S |

### 3.2 Patients and consent
| ID | Requirement | P |
|---|---|---|
| FR-P1 | The system shall register patients with demographics and contacts. | M |
| FR-P2 | The system shall warn on likely duplicates using deterministic matching and require human review before merging. | M |
| FR-P3 | The system shall capture consent with purpose and timestamp, using clinic-configurable text. | M |
| FR-P4 | The system shall support caregiver/proxy access with recorded authority. | S |

### 3.3 Scheduling and queue
| ID | Requirement | P |
|---|---|---|
| FR-S1 | Staff shall book, reschedule, and cancel appointments by branch, clinician, and service. | M |
| FR-S2 | The system shall manage walk-ins in a queue with statuses (booked, waiting, in consult, done, no-show). | M |
| FR-S3 | The system shall send SMS/WhatsApp reminders via a provider adapter, with retries on failure. | M |
| FR-S4 | The system shall track no-shows and report rates. | S |

### 3.2b Clinical records
| ID | Requirement | P |
|---|---|---|
| FR-R1 | The system shall record encounters with vitals, history, allergies, problems, diagnosis, notes, and attachments. | M |
| FR-R2 | The system shall record prescriptions linked to an encounter. | M |
| FR-R3 | Clinical corrections shall create a new version; prior versions shall remain viewable. | M |
| FR-R4 | A clinician shall be able to approve a patient-facing summary. | M |

### 3.3b Offline and sync
| ID | Requirement | P |
|---|---|---|
| FR-O1 | Registration, appointment viewing, vitals, notes, and prescription drafts shall work offline. | M |
| FR-O2 | Offline writes shall be stored in a local outbox and synced automatically when connectivity returns. | M |
| FR-O3 | Each write shall carry an idempotency key; the server shall ignore duplicate deliveries. | M |
| FR-O4 | On conflict, the system shall keep both versions and flag them for clinician resolution. | M |
| FR-O5 | The UI shall show per-record sync state (pending, syncing, synced, failed). | M |
| FR-O6 | The system shall never silently discard a clinical write. | M |

### 3.4 Teleconsult
| ID | Requirement | P |
|---|---|---|
| FR-C1 | Clinicians shall publish availability; patients shall book remote slots. | M |
| FR-C2 | Before a consult, the system shall collect intake, consent, and red-flag screening. | M |
| FR-C3 | The system shall provide secure chat and browser video through a provider adapter. | M |
| FR-C4 | The system shall degrade gracefully from video to audio to text under poor connectivity. | M |
| FR-C5 | The clinician shall record a consultation note, prescription, follow-up, and optional referral. | M |
| FR-C6 | If red flags are present, the system shall advise in-person care and record the escalation. | M |

### 3.5 Billing
| ID | Requirement | P |
|---|---|---|
| FR-B1 | The system shall create invoices linked to encounters or services. | M |
| FR-B2 | The system shall record payments by gateway, cash, or transfer, and issue receipts. | M |
| FR-B3 | Refunds shall require role-separated approval. | M |
| FR-B4 | Payment webhooks shall be verified and processed idempotently. | M |
| FR-B5 | The system shall produce a daily reconciliation report. | S |

### 3.6 Audit and privacy
| ID | Requirement | P |
|---|---|---|
| FR-A1 | The system shall write an append-only audit event for every PHI read, create, update, export, and share. | M |
| FR-A2 | Audit events shall record actor, patient, action, purpose, time, and device. | M |
| FR-A3 | Admins shall be able to view and filter access history. | M |
| FR-A4 | Retention and deletion rules shall be configurable per tenant. | S |

### 3.7 Interoperability and referral
| ID | Requirement | P |
|---|---|---|
| FR-I1 | The system shall export patient, encounter, observation, medication, and consent data in a FHIR-aligned format. | S |
| FR-I2 | A patient-approved summary shall be shareable with another clinic and revocable. | S |
| FR-I3 | External integrations shall sit behind adapter interfaces and queues. | M |

## 4. External interface requirements

- **User interface:** responsive web app; PWA install; low-bandwidth friendly; clear offline and sync indicators; keyboard and screen-reader accessible
- **API:** versioned REST/JSON; authentication via short-lived tokens; documented via OpenAPI
- **Provider adapters:** SMS/WhatsApp, payments, video, email; retryable and replaceable
- **Hardware:** low-end smartphones and basic laptops

## 5. Non-functional requirements

### 5.1 Performance (proposed targets)
- API p95 under 500 ms for common reads under normal load
- Initial staff app load usable on a slow 3G connection within [X] seconds, to be measured
- Outbox sync of 100 queued writes completes within [X] minutes of reconnection

### 5.2 Reliability
- Proposed RPO ≤ 15 minutes, RTO ≤ 4 hours for the MVP
- Backups encrypted; restore tested at least once before pilot and then on a schedule
- Queue-backed jobs with retries and circuit breakers for providers

### 5.3 Security
- TLS everywhere; encryption at rest with managed key service
- Tenant isolation enforced at API and database layers (row-level)
- Least-privilege RBAC; MFA for privileged roles
- Secrets in a secrets manager; dependency and vulnerability scanning
- Logs minimise PHI

### 5.4 Privacy and compliance
- Consent and purpose recorded for access and sharing
- Designed to support NDPA 2023 obligations; a privacy impact assessment is required before production
- Clinician licence verification configurable
- Not a compliance certification or legal advice

### 5.5 Usability
- Core front-desk flows learnable without training documents
- Error messages explain what to do next

### 5.6 Maintainability and observability
- Modular code by domain; automated tests; infrastructure as code
- Metrics: sync lag, failed jobs, consult completion, uptime, export latency
- Structured logs, alerting, incident runbooks

### 5.7 Safety
- The system does not provide autonomous diagnosis
- Remote care is limited to configured protocols with red-flag escalation

## 6. Data requirements

- Canonical model aligned to FHIR resources: Patient, Practitioner, Encounter, Observation, DiagnosticReport, MedicationRequest, CarePlan, Consent
- Core tables: tenant, branch, staff, patient, consent, appointment, encounter, observation, prescription, referral, invoice, payment, audit_event
- Every clinical row carries tenant_id, created/updated by and at, and a version
- Attachments in object storage with encrypted backups

## 7. Acceptance criteria (examples)

| Requirement | Test |
|---|---|
| FR-T3 | A user from Tenant A requesting a Tenant B record receives no data; automated test covers every endpoint |
| FR-O3 | Replaying the same write 3 times creates one record |
| FR-O4 | Two offline edits to one record produce two preserved versions flagged for review |
| FR-O6 | Killing the network mid-sync loses no queued writes |
| FR-A1 | Viewing a patient record creates one audit event |
| FR-B4 | A replayed payment webhook does not double-credit an invoice |
| FR-C4 | Throttling bandwidth switches a consult from video to audio, then text |

## 8. Traceability

PRD items P-01 to P-12 map to FR groups: P-01 → 3.1; P-02 → 3.2; P-03/P-04 → 3.3; P-05 → 3.2b; P-06 → 3.3b; P-07 → 3.4; P-08 → 3.5; P-09 → 3.6; P-10/P-12 → 3.7; P-11 → 5.6.

## 9. Open issues

- Exact consent text and licensing checks per clinic type
- Provider selection and cost
- Data-residency requirements
- Conflict-resolution UX for clinicians
