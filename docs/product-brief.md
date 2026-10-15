# Product brief

Africa-first clinic management, telemedicine, and longitudinal health-record platform

**Region:** Nigeria first; designed for West Africa and later other African and emerging markets

> This is the original brief the project is built from, kept word for word.
> How the build matches it is tracked in [brief-alignment.md](./brief-alignment.md).

## Product thesis

Design judgment: Nigerian clinics need one operational system that works through unreliable connectivity instead of separate appointment, video, billing, and record tools. The differentiated wedge is an offline-first, low-bandwidth clinic OS combining front-desk/workflow automation with clinician teleconsults and a patient-controlled, portable longitudinal record. Start with private primary-care and specialist clinics in Nigeria, encode Nigerian consent, privacy, licensing, payment, and referral workflows, and expose standards-based APIs so the product can later connect to insurers, labs, pharmacies, hospitals, and public-health systems. This is not a claim that every clinic has the same need; validate the wedge with 10-20 clinics before broadening scope.

## Target users

- Small and mid-sized private clinics and multi-site outpatient groups in Nigeria
- Clinicians and care teams providing in-person, asynchronous, or video consultations
- Patients and caregivers who need affordable follow-up, referrals, prescriptions, and access to their records
- Employers, HMOs, labs, pharmacies, and specialist networks consuming referral, claims, or care-plan APIs

## Core workflows

- **Clinic onboarding:** configure branches, departments, staff roles, services, prices, schedules, consent text, and escalation rules.
- **Patient registration and identity resolution:** create or match a patient, capture consent and contacts, support caregiver/proxy access, and prevent duplicate records.
- **Appointment and queue management:** book online, by phone, or at the front desk; send SMS/WhatsApp reminders; support walk-ins, triage, rescheduling, and no-show tracking.
- **Encounter and longitudinal record:** capture vitals, history, allergies, diagnosis, notes, orders, results, care plans, attachments, prescriptions, and a tamper-evident audit trail, with offline sync.
- **Telemedicine:** clinician availability, pre-consult intake, consent, low-bandwidth video or audio fallback, chat, clinical note, prescription/referral, follow-up, and escalation to physical care.
- **Payments and revenue operations:** invoices, receipts, deposits, refunds, reconciliation, configurable cash/transfer/card/mobile-money rails, and exportable clinic reports.
- **Referral and continuity of care:** share a patient-approved summary with another clinic or specialist, receive lab/diagnostic results, and let the patient download or grant access to records.

## Production architecture

- **Frontend:** responsive React/Next.js web app for staff plus a PWA with IndexedDB/outbox sync for intermittent connectivity; a lightweight patient web experience rather than requiring a native app initially.
- **Backend:** modular TypeScript service (or Go equivalent) with REST/JSON APIs, background jobs, tenant/branch/role authorization, idempotency keys, and domain modules for scheduling, encounters, billing, telehealth, and referrals.
- **Clinical data:** PostgreSQL with tenant and row-level isolation, append-only audit events, object storage for documents, encrypted backups, and a FHIR-aligned canonical model for Patient, Practitioner, Encounter, Observation, DiagnosticReport, MedicationRequest, CarePlan, and Consent.
- **Interoperability:** versioned FHIR-style API and export/import layer; adapters for labs, pharmacies, HMOs/insurers, SMS/WhatsApp, email, payments, identity verification, and video; keep vendor adapters behind queues and retryable interfaces.
- **Security and privacy:** TLS everywhere, encryption at rest with managed KMS, short-lived tokens, MFA for privileged staff, least-privilege RBAC/ABAC, consent and purpose tracking, immutable access logs, secrets management, device/session revocation, and configurable retention/deletion workflows aligned to Nigerian privacy obligations.
- **Reliability and offline behavior:** transactional outbox, idempotent sync, conflict-resolution rules for clinical data, queue-backed notifications, circuit breakers, rate limits, graceful audio/text fallback for teleconsults, and tested RPO/RTO backups.
- **Observability and safety:** structured logs with PHI minimization, metrics for sync lag, failed jobs, consultation completion, uptime, and data-export latency; distributed tracing, alerting, incident runbooks, clinical safety review, and audit dashboards for clinic administrators.
- **Deployment:** containerized services on a managed cloud in a region acceptable to customers, infrastructure as code, separate dev/staging/prod accounts, automated migrations with rollback, blue-green/canary releases, vulnerability scanning, dependency/SBOM checks, and disaster-recovery restore tests.

## Monetization

- B2B SaaS subscription per clinic branch with tiered limits for staff, locations, records, and teleconsult volume; charge in naira with annual and monthly options.
- Usage-based fees for completed teleconsults, outbound SMS/WhatsApp notifications, storage, and premium video, with transparent pass-through for communications and payment costs.
- Enterprise/API contracts for multi-site clinic groups, HMOs, employers, labs, and pharmacy networks with SSO, dedicated support, data-export controls, SLAs, and implementation fees.
- Design judgment: avoid selling identifiable patient data; optional aggregate, de-identified analytics should require explicit governance, contracts, and customer opt-in.

## Why now

Sourced context: WHO estimates an 11 million health-worker shortfall by 2030, mostly in low- and lower-middle-income countries, increasing the value of workflow efficiency, triage, and remote specialist access. GSMA reports that Sub-Saharan Africa had 527 million unique mobile subscribers and 27% mobile-internet penetration at end-2023, with a 60% usage gap; it forecasts 4G at 50% of connections by 2030. That supports a mobile, low-bandwidth product but argues against assuming always-on video. Nigeria's official data-protection framework is now established through the Nigeria Data Protection Act 2023 and NDPC, while MDCN guidance explicitly requires confidentiality and explicit written consent for identifiable clinical material shared online. WHO and HL7 have also identified interoperability as critical to continuity of care and describe FHIR as an API-based open data-exchange standard. Design judgment: these conditions make an offline-first, consent-aware, FHIR-aligned clinic platform more timely than a video-only telehealth app; timing still depends on local validation, licensing interpretation, and willingness to pay.

## Risks and controls

- **Patient safety and misdiagnosis in remote care:** limit telemedicine to appropriate protocols, require red-flag triage and in-person escalation, clinician licensing checks, structured notes, consent, follow-up, and clinical governance; do not market the system as autonomous diagnosis.
- **Privacy breach or inappropriate staff access:** apply least privilege, MFA, encryption, tenant isolation, immutable audit logs, consent/purpose controls, PHI-minimized observability, incident response, and a Nigerian privacy impact assessment before production.
- **Regulatory uncertainty across Nigerian states and later countries:** obtain counsel and regulator engagement, keep provider verification and consent configurable, maintain a country-by-country compliance matrix, and launch only in services and jurisdictions cleared by local professionals.
- **Connectivity, power, and video unreliability:** make scheduling, notes, messaging, prescriptions, and sync usable offline; support SMS/voice/audio fallback; queue retries; show sync state; and never silently discard clinical writes.
- **Bad data, duplicate patients, or unsafe record merges:** use deterministic plus human-reviewed matching, provenance, versioning, clinician correction workflows, export/restore tests, and conflict rules that preserve rather than overwrite clinical history.
- **Fraud, payment failure, and commercial leakage:** idempotent billing, reconciliation, role-separated approval, signed receipts, webhook verification, configurable cash workflows, and reporting that surfaces unusual refunds or discounts.
- **Low adoption and weak unit economics:** co-design with clinics, start with measurable operational wins such as reduced waiting time and no-shows, provide migration/import tools and onboarding, price for local purchasing power, and gate expansion on retention, paid conversion, consultation completion, and support cost.

## MVP scope

- Multi-tenant clinic administration with branches, users, roles, services, schedules, patient registration, duplicate warnings, consent capture, and audit log.
- Appointment, queue, triage, reminders, and no-show workflows with one SMS/WhatsApp provider and an admin notification console.
- Core longitudinal record for demographics, encounters, vitals, problems, allergies, notes, attachments, prescriptions, and clinician-approved patient summary; implement offline draft/outbox sync for the highest-value flows.
- Teleconsult flow with clinician availability, patient intake, consent, secure chat, browser video, audio/text fallback, consultation note, follow-up, and referral; integrate one video provider behind an adapter.
- Billing basics: invoice, receipt, payment status, refunds, daily reconciliation, and one Nigerian payment gateway plus manual cash/transfer recording.
- Interoperability and governance slice: FHIR-aligned export for patient/encounter/observation/medication/consent, role-based access, access history, retention settings, backup/restore, and a privacy/incident runbook.
- Operational proof: dashboards for wait time, no-shows, consultation completion, sync failures, revenue, and record-access events; pilot with a small set of Nigerian clinics and run restore and offline-chaos tests before adding AI or broad marketplace features.

## Expansion path

Design judgment: first win Lagos/Abuja and one secondary Nigerian market through private outpatient clinics, then expand to multi-branch groups and HMO/employer referrals using the same tenant, billing, and FHIR layers. Next add West African adapters rather than forking the core: country-specific provider verification, consent language, data-residency options, tax/payment rails, SMS channels, and telemedicine rules for Ghana, Kenya, and francophone markets. Package a partner/API edition for labs, pharmacies, insurers, and hospital referrals. Longer term, sell the portable-record and interoperability layer to regional networks and diaspora-linked care, while keeping clinical decisions with licensed local providers. Reuse the offline sync, standards model, and operational playbooks globally; localize regulation, identity, language, pricing, and payment country by country.

## Evidence sources

1. **WHO Health workforce:** WHO estimates a projected shortfall of 11 million health workers by 2030, mostly in low- and lower-middle-income countries.
2. **The Mobile Economy Sub-Saharan Africa 2024:** GSMA reports 527 million unique mobile subscribers and 27% mobile-internet penetration in Sub-Saharan Africa at end-2023, a 60% usage gap, and forecasts 4G at 50% of connections by 2030.
3. **WHO and HL7 collaborate to support adoption of open interoperability standards:** WHO says interoperability standards are critical for consistent health-data representation and continuity of care, and identifies HL7 FHIR as an API-based open data-exchange standard.
4. **FHIR Overview, HL7:** HL7 defines FHIR as a standard for exchanging healthcare information electronically and describes resources, security/privacy, clinical, workflow, and financial modules.
5. **Nigeria Data Protection Commission; MDCN Guidance on Social Media and Responsible Online Conduct:** Nigeria's official privacy regulator is established under the Nigeria Data Protection Act 2023, and the official MDCN guidance says identifiable patient information should not be shared without explicit written consent and that online conduct must comply with Nigerian data-protection law. Sources: https://ndpc.gov.ng/ and https://www.mdcn.gov.ng/public/storage/documents/document_904463861.pdf
