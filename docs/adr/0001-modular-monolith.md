# ADR-0001: Modular monolith organised by feature

- **Status:** Accepted
- **Date:** 2026-10-06

## Context
The platform will grow across many areas (patients, scheduling, records, telehealth, billing, referrals, interoperability) and will be built by one developer first. We need a structure where changing or adding a feature touches few files and where parts cannot break each other by accident.

## Options considered
1. **Folders by technical layer** (routers/, models/, services/). Every feature touches many folders and any file can import any other, so coupling grows silently.
2. **Microservices.** Too much operational weight for one developer and for unreliable-connectivity deployments.
3. **Full hexagonal architecture everywhere.** More ceremony than the MVP needs.
4. **Modular monolith by feature, with adapters only at external boundaries.** One deployable app, clear module borders.

## Decision
Option 4.

- Backend: `app/core` for shared plumbing and `app/modules/<name>` for each business area. Each module follows the same shape: router, schemas, service (the public door), repository, models, events, adapters, tests.
- Frontend: `src/features/<name>` mirrors backend modules; `src/app` holds thin routes only.
- Dependencies point one way: router, then service, then repository. Modules call each other's **service**, never each other's repository or models.
- Cross-module side effects (audit, notifications) travel as events.
- Modules reference each other's data by ID.
- External providers (SMS, payments, video, labs) sit behind adapters with fake versions for tests.
- One Alembic history; module models are registered in `app/model_registry.py`.
- CI enforces boundaries with import-linter. Today it checks that `core` never imports `modules`; stricter per-module rules are added as modules gain code.

## Consequences
- Adding a feature usually means adding a module folder rather than editing existing ones.
- A module can later be extracted into its own service because it already talks through services and events.
- Cost: some discipline and a few extra files per module.
- Revisit if the team grows or a module needs independent scaling.
