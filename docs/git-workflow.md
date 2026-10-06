# Git workflow

## Branches
- `main` is always working. Work on short branches: `feat/patient-registration`, `fix/sync-duplicate`, `docs/adr-auth`.
- Open a pull request into `main` even when working alone. The CI run and the checklist in `.github/pull_request_template.md` are your review.

## Commit messages
Format: `type(scope): what changed`, present tense, under about 70 characters.

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`.
Examples:
- `feat(patients): add patient model and migration`
- `test(tenancy): cover cross-tenant read returns 404`
- `refactor(scheduling): move queue rules into service`

## What makes a good commit
One idea, leaves the project working, and you can say in one line why it exists. Commit after each green step: a model, then its migration, then its service with a test, then its router, then its screen. That naturally gives several meaningful commits a day.

## Never commit
`.env`, real patient data (even in screenshots), generated build folders, credentials of any kind.

## First day: suggested commit sequence
1. `chore: add gitignore and env example`
2. `docs: add README, PRD, SRS and interview questions`
3. `docs: record modular monolith decision (ADR-0001)`
4. `chore(backend): add FastAPI skeleton with health endpoints`
5. `feat(tenancy): add tenant and branch models with first migration`
6. `feat(core): add in-process event bus with test`
7. `chore(frontend): add Next.js skeleton and feature folders`
8. `chore(docker): add compose for db, redis, api and web`
9. `ci: add GitHub Actions with migration round trip and import check`
10. `docs(agent): add project skills for the coding agent`

Read each part as you commit it. A history you understand is worth more than a long one.
