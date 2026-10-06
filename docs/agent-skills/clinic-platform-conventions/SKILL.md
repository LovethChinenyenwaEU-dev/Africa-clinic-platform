---
name: clinic-platform-conventions
description: Project conventions, stack, repo layout, scope limits and definition of done for the Africa-first Clinic Platform (FastAPI, Next.js, PostgreSQL, Redis, Docker). Use this skill at the start of ANY task in this repo, including adding endpoints, models, migrations, screens, tests or docs, and whenever the user asks what to build next, what is in or out of MVP scope, or how code should be structured, even if they do not mention conventions.
---

# Clinic Platform conventions

## What this project is
A multi-tenant, offline-first clinic management, telemedicine and health-record platform for Nigerian clinics. Read `PRD.md` and `SRS.md` in the repo root when a requirement is unclear; requirement IDs (e.g. FR-O3) come from the SRS.

## Stack
- Backend: Python, FastAPI, SQLModel, Alembic, PostgreSQL, Redis (jobs), pytest
- Frontend: Next.js, React, Tailwind, PWA with IndexedDB
- Tooling: Docker Compose, GitHub Actions CI

## Repo layout (keep modules separate by domain)
```
backend/app/{tenancy,patients,scheduling,records,telehealth,billing,referrals,audit,interop}/
backend/app/core/{auth,db,config,jobs}/
backend/alembic/
frontend/src/{app,features,lib/sync}/
```
Each domain module owns its models, schemas, routes, services and tests. Do not import one module's internals from another; call its service functions.

## Rules
1. **Vertical slices.** Finish one flow end to end (migration, model, API, test, screen) before starting another.
2. **Tenant scoping and audit are mandatory** on anything touching patient data. Load `clinic-tenant-isolation-rbac` and `clinic-consent-audit-privacy` for those tasks.
3. **Writes that can happen offline** must follow `clinic-offline-sync-outbox`.
4. **External services** (SMS, payments, video, labs) go behind adapters. Load `clinic-fhir-export-adapters`.
5. **Schema changes only through Alembic migrations.** Never edit the database by hand.
6. **No real patient data** in code, tests, fixtures, logs or screenshots. Use clearly fake data.
7. Never commit secrets; use environment variables and `.env.example`.

## Scope guard (MVP)
In scope: tenancy, patients and consent, scheduling and queue, reminders, records, offline sync, teleconsult, billing basics, audit, FHIR-aligned export, dashboards.
Out of scope: AI diagnosis or suggestions, provider marketplace, native apps, insurance adjudication, non-Nigerian rollout. If asked for these, say they are post-MVP and propose the smallest MVP-compatible alternative.

If behind schedule, cut in this order: video (keep chat), payment gateway (keep manual recording), dashboards.

## Safety rules
- The product never gives autonomous diagnosis. Remote care needs red-flag triage and an in-person escalation path.
- Clinical data is never silently deleted or overwritten; corrections create new versions.
- Do not state that the system is legally compliant or clinically safe. Say it is designed to support those goals pending professional review.

## Definition of done
- [ ] Code follows module boundaries
- [ ] Migration included and reversible
- [ ] Tests added, including a tenant-isolation test for new patient-data endpoints
- [ ] Audit event written for any PHI read or write
- [ ] No PHI in logs
- [ ] OpenAPI docs updated; README roadmap checkbox ticked if a week's goal is met
- [ ] Short note on what changed and any open questions

## Working style
Before large changes, state the plan in 3 to 6 lines and the SRS requirement IDs it satisfies. Prefer small commits. When a requirement conflicts with the SRS, flag it instead of silently deviating.
