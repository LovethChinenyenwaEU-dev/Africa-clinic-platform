# ADR-0004: Python and FastAPI for the backend

- **Status:** Accepted
- **Date:** 2026-10-15

## Context
The product brief asks for "a modular TypeScript service (or Go equivalent)". The backend
was built in Python with FastAPI, SQLModel and Alembic from Week 1, and by Week 7 it has
about 630 passing tests. The README, PRD and SRS name this stack, but no decision record
explained why it differs from the brief. This record closes that gap.

## Options considered
1. **Rewrite in TypeScript** to match the brief's wording. Several weeks of rework before
   offline sync, teleconsult and billing can start; every backend test rewritten.
2. **Keep Python and FastAPI**, and meet what the brief actually needs from the backend:
   modular domains, REST/JSON, background jobs, tenant and role authorisation, idempotency.

## Decision
Option 2.

- The brief's "(or Go equivalent)" shows the requirement is a modular, typed, reliable
  service, not one language. Everything else the brief asks of the backend is met the same
  way (ADR-0001 modules, import-linter boundaries, adapters, queue-backed jobs).
- Python is the language the developer works fastest and most safely in; the frontend is
  already TypeScript, so the team still uses both.
- Types are enforced at the edges: Pydantic validates every request and response, and the
  frontend checks every answer again with Zod.
- Python has mature health-data tooling (for example FHIR resource libraries) for the
  Week 11 export.

## Consequences
- The backend and frontend do not share type definitions directly. If drift becomes a
  problem, generate TypeScript types from the backend's OpenAPI document.
- A future team that prefers TypeScript can replace one module at a time: modules already
  talk through services and IDs (ADR-0001).
- Revisit if hiring, performance, or a partner's requirements make another language
  clearly better.
