# Build log

One entry per working day, newest first. Each entry says what was done, the hardest
problem and how it was solved, what broke and how it was fixed, what is finished, what is
pending, and what comes next. Test counts are from the Codespace (backend: `pytest`,
frontend: `npm test`).

Roadmap: [README](./README.md#roadmap-12-week-mvp) · Brief: [docs/product-brief.md](./docs/product-brief.md) · Brief check: [docs/brief-alignment.md](./docs/brief-alignment.md)

---

## 16 Oct 2026 (Fri): Week 8 Steps 1–2

**Done**
- Week 8 Step 1 (written on 15 Oct) confirmed in the Codespace: migration 0013 up and down, backend tests green, 156 frontend tests. A write sent twice with the same `Idempotency-Key` now happens once (the SRS acceptance test: 3 sends, 1 record).
- Week 8 Step 2: every audit line records **which device** it came from (FR-A2). Each browser keeps a random device ID (not a fingerprint), sends it as `X-Device-Id`, the pass-through forwards it only if it is a proper UUID, and the admin audit log shows a Device column.

**Hardest problem: getting the device into every diary line without touching dozens of service calls**
- *Fix:* the device is read once per request into a per-request context variable that the diary reads by itself. A test proves one request's device never leaks into the next, and work done outside a request (the reminder worker) records no device.

**Broke, and fixed**
- *A proxy test used a header value with a line break:* real `Headers` objects refuse those before our code runs, so the test would have failed for the wrong reason. Replaced with a plain malformed value.

**Finished:** Week 8 Steps 1–2 (Step 2 awaiting its Codespace run).

**Pending:** as on 15 Oct.

**Next:** Step 3, keeping conflicting offline corrections (both versions kept and flagged for a clinician).

---

## 15 Oct 2026 (Thu): Week 7 finished; sign-in in Codespaces; brief review

**Done**
- Sign-in from the Codespace address works (it was refused with 403).
- `reset-demo-passwords` command (development only, demo logins only).
- Ran a complete visit on the real stack: front desk checks in, doctor starts the visit, records vitals, allergy, diagnosis and note, signs off.
- Step 4c: the queue shows visits left open from earlier days in a separate box, so yesterday's walk-in no longer sits at #1.
- Step 5: audit log viewer for admins (staff, patient and day filters; patients shown by ID only).
- Week 7 wrap-up in the README (demo data, Codespaces notes).
- Saved the product brief in `docs/` and checked the whole build against it (`docs/brief-alignment.md`).
- Week 8 planned (8 steps) and Step 1 written: the `Idempotency-Key` header.

**Hardest problem: sign-in refused (403) only in Codespaces**
- *Cause:* the sign-in route's anti-forgery check compares the browser's `Origin` with the server's own address. The Codespaces proxy **rewrites `Origin` to `https://localhost:3000`** and puts the real address in `x-forwarded-host`, so they never matched.
- *How it was found:* guessing failed twice (a `TRUSTED_ORIGINS` setting did not help, because the origin it would match had been rewritten). A development-only log of the three headers showed the real values at once.
- *Fix:* accept an origin that matches **either** `x-forwarded-host` **or** `host`. Still safe: a forged cross-site request carries the attacker's own origin, which matches neither. Two tests use the exact headers from the log.
- *Lesson:* when a guess fails, measure before guessing again.

**Broke, and fixed**
- *Web container kept "stopping":* the Codespace itself had stopped (idle timeout), which stops every container (`Exited (255)`). Fix: `docker compose up -d` after any Codespace stop (now in the README).
- *Forgot the demo password:* added `reset-demo-passwords`, restricted to `@demo.example.com` and to development/test, so it can never change a real login.
- *Windows Defender now blocks `node.exe` on the laptop* (it already blocked Python). Frontend tests now run in the Codespace too.
- *Audit log showed "Unknown staff" for everyone once:* a one-off failure loading the staff list; the screen failed silently. It now shows an explanation if the list cannot load. The next load showed names correctly.
- *Refusal log printed during tests:* now only in `development`.

**Finished:** Week 7. Tests: 633 backend, 155 frontend, ruff and import boundaries clean.

**Decisions**
- Backend stays Python + FastAPI (the brief says TypeScript/Go): recorded in ADR-0004.
- Roadmap extended from the brief review: patient web experience, schedules, triage (W9); services and prices (W10); admin screens, notification console, database row-level security, tamper-evident audit, MFA, device revocation (W11).
- Week 8 offline rules: (1) minimal patient data on the device (today's queue and encounters open on it), wiped at sign-out (blocked while unsent writes remain) and after 24 hours; (2) vitals/notes taken before sign-off but synced after it are accepted and marked "synced late", with a notice to the doctor; (3) patient registration works offline, and a possible duplicate becomes a "needs review" item on sync.

**Pending (carried forward)**
- Real SMS provider adapter.
- Test dates are fixed at 2 Nov 2026: move them later before that date.
- Reschedule button on the queue screen (backend done).

**Next:** Week 8, offline sync and conflict handling.

---

## 14 Oct 2026 (Wed): Week 6 finished; Week 7 screens

**Done**
- Week 6 Steps 4–6 tested green (allergies/problems, notes, clinical endpoints).
- Week 6 Step 7: the audit diary records **which record** was touched; admins filter by staff and date. Week 6 ticked.
- Week 7 Step 1: Tailwind 4, with existing styles moved into CSS layers.
- Step 2: server pass-through `/api/backend/...` (the login token never reaches the browser) and the role-based app shell.
- Step 3: patient search, registration with the duplicate question, patient page with consent.
- Step 4a: queue screen; backend gained patient names on the queue, a Lagos-day visit list and a clinician list.
- Step 4b: `seed-demo` command, "Start visit", and the encounter screen (vitals, allergies, problems, notes, sign-off).

**Hardest problem: a correct-looking queue that was unusable**
- The queue returned IDs only (an earlier "no names" choice), there was no list of today's booked visits, and front desk could not list clinicians.
- *Fix:* names-only lookup in one query (no per-patient diary lines), a day list bounded by **Lagos** midnight, and an ID/name/role-only clinician list. The privacy choice (full name on the staff queue) was made explicitly.

**Broke, and fixed**
- *Codespace web app: "Cannot find module '@tailwindcss/postcss'".* The container keeps its own `node_modules` volume from before Tailwind. Fix: `docker compose up -d --build --renew-anon-volumes web`.
- *Two commits had the same message* (the second swallowed most of the files). Left as is, because rewriting pushed history is riskier. Habit adopted: `git status` before every commit.
- *Stale generated types after moving a page* broke the build. Fix: clear `.next/dev`.
- *Vitals errors showed internal names* ("temperature_c must be…"). Fix: staff wording ("Temperature (°C) must be…").
- *One-tap Cancel/No-show on final actions.* Added an "are you sure?" step, because those moves cannot be undone.

**Finished:** Week 6. Week 7 Steps 1–4b. Tests: 617 backend, 140 frontend.

**Pending:** Codespaces sign-in (403), Step 5 audit viewer.

**Next:** fix sign-in in Codespaces, then the audit viewer.

---

## 13 Oct 2026 (Tue): Week 4 finished; Week 5 reminders; Week 6 started

**Done**
- Week 4 scheduling finished (booking, walk-ins, queue, check-in, cancel, no-show, reschedule). README roadmap fixed.
- Week 5, all six steps: message adapter (fake/none), `reminder` table, reminders follow bookings, sender with locking + retries + backoff, background worker with a Redis heartbeat, consent check at send time. Week 5 ticked.
- Week 6 Steps 1–3: `encounter` table; open/close/mistake rules (only the clinician who opened it signs off, by your decision); vitals with typo-only ranges and corrections as versions.
- Week 6 Steps 4–6 written (allergies/problems, notes, endpoints) for testing next day.

**Hardest problem: no way to run tests on the laptop**
- Windows blocked Python ("virus or potentially unwanted software") and WSL/Docker was broken.
- *Fix:* moved testing to GitHub Codespaces: push from the laptop, `git pull` and `docker compose exec api pytest` in the Codespace.

**Broke, and fixed**
- *3 reminder table tests failed* after bookings started creating reminders automatically (duplicate key). The rule was right, the tests were stale. Fix: those tests use walk-ins, which get no automatic reminder.
- *Ruff:* one blank line too many after imports. Fixed to match `--fix`.
- *Tests "not found" in the Codespace:* it had not pulled yet. Habit: pull before testing.

**Finished:** Week 4, Week 5. Tests: 493 backend.

**Next:** test Week 6 Steps 4–6.

---

## 12 Oct 2026 (Mon): frontend login *(rebuilt from git history)*

**Done:** login page, signed-in home page and error page; login form and sign-out; TanStack Query; `getCurrentUser` for pages; allowed Codespaces origins for the dev server; tests for the login client, form errors and role labels.

---

## 11 Oct 2026 (Sun): consent, audit diary, frontend foundations *(rebuilt from git history)*

**Done:** patient endpoints (guarded, audited, clinic-scoped); consent (versioned wording, grant, revoke, history) with endpoints; append-only audit diary with an admin-only reader that logs its own reads; ADR-0003 (patient data rules); frontend Zod schemas, session route (login, current user, logout) with httpOnly cookie and origin check; upgrade to Next.js 16 and React 19.

**Broke, and fixed (from commits):** `@types/node` clashed with Vitest/Vite (aligned the versions); CI switched to Node 22 and `npm ci` for reproducible installs; generated `next-env.d.ts` ignored.

---

## 10 Oct 2026 (Sat): login, staff, branches, permissions, patients *(rebuilt from git history)*

**Done:** `/auth/me` and the login guard; tenant-scoped query helpers with clinic-wall tests; branch endpoints; one roles-to-capabilities table and the `require(capability)` guard; staff management for admins (last-admin rule); a test that fails if any route lacks the login guard; patient model, migration and phone normalisation; ADR-0002; Weeks 1–2 ticked.

---

## 9 Oct 2026 (Fri): access tokens and login *(rebuilt from git history)*

**Done:** access tokens (PyJWT) with longer secret keys; login service, endpoint and validation; shared database fixtures for tests.

---

## 8 Oct 2026 (Thu): passwords, staff, first clinic *(rebuilt from git history)*

**Done:** password hashing (argon2) and password rules; `create_staff`; `create_tenant`; `provision_clinic` and the `create-clinic` command.

---

## 7 Oct 2026 (Wed): staff table, CI fixes *(rebuilt from git history)*

**Done:** staff model, roles and migration (unique email).

**Broke, and fixed (from commits):** CI lint failures: ruff rules made explicit, and ruff told that `alembic` is a third-party package.

---

## 6 Oct 2026 (Tue): project foundation *(rebuilt from git history)*

**Done:** README, PRD, SRS, interview questions, git workflow; ADR-0001 (modular monolith); FastAPI skeleton with health endpoints; tenant and branch models with the first migration; in-process event bus; Next.js skeleton; Docker Compose (db, redis, api, web); GitHub Actions CI with a migration round trip and import check; coding-agent skills.

---

## How to add an entry

Copy this block to the top, under the line, and fill it in at the end of each working day:

```markdown
## DD Mon YYYY (Day): short title

**Done**
-

**Hardest problem:** what it was, the cause, the fix, the lesson.

**Broke, and fixed**
-

**Finished:**   Tests: N backend, N frontend.

**Pending:**

**Next:**
```
