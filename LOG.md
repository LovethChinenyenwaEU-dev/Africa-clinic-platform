# Build log

One entry per working day, newest first. Each entry says what was done, the hardest
problem and how it was solved, what broke and how it was fixed, what is finished, what is
pending, and what comes next. Test counts are from the Codespace (backend: `pytest`,
frontend: `npm test`).

Roadmap: [README](./README.md#roadmap-12-week-mvp) · Brief: [docs/product-brief.md](./docs/product-brief.md) · Brief check: [docs/brief-alignment.md](./docs/brief-alignment.md)

---

## 21 Oct 2026 (Wed): Week 9 Step 8a, the patient web pages (sign-in, visits, summaries)

**Done**
- Week 9 Step 7 (patient summary) confirmed green in the Codespace.
- Week 9 Step 8a: **patients sign in and see their own record.** Each clinic has a patient link (`/patient/<clinic ID>`, shown on the staff home page for front desk to share). The patient types their phone number and date of birth; if both match exactly one patient of that clinic, a 6-digit code goes by SMS. The answer is the same either way, so nobody can find out who is registered. The code lasts 10 minutes, works once, allows 5 tries, and at most 3 are sent per phone every 15 minutes; only a keyed hash is stored. In development (SMS off) the code is shown on screen. The patient then sees their upcoming and past visits and the summaries their clinician approved (never drafts or withdrawn ones). Patients have their own token (marked as a patient token) and their own httpOnly cookie and pass-through: a patient token is refused on staff doors and a staff token on patient doors. Every patient action is in the audit log with the patient as the actor; the admin audit log shows it as "The patient, on their own page". Migration 0024.

**Hardest problem:** families sharing one phone. A code to "whoever owns this number" would open a sibling's or a parent's record. *Fix:* phone **and** date of birth must match exactly one patient before any code is sent; a test signs a child in on the mother's phone.

**Broke, and fixed**
- *Shell commands with an apostrophe in the text failed before running* (nothing was written): files with such text are now written with the editor instead.

**Finished:** Week 9 Steps 1–7. Step 8a written, awaiting its Codespace run (needs `alembic upgrade head`). Migration head: 0024.

**Pending:** as on 16 Oct. A real SMS provider is now needed for patient sign-in outside development.

**Next:** Week 9 Step 8b: on the patient pages, consent to remote care, book a remote slot, do the intake, join the consult and chat.

---

## 19 Oct 2026 (Mon): Week 9 Step 7, the patient summary

**Done**
- Week 9 Step 6 (follow-up and referral) confirmed green in the Codespace.
- Week 9 Step 7: **the clinician-approved patient summary** (FR-R4). On the encounter, a doctor or nurse drafts a plain-language summary; "Start from this visit" fills in this visit's diagnoses, the active medicines, follow-ups and referrals, and always ends with when to seek urgent help. It leaves out the clinicians' own words (follow-up instructions, referral reasons). Only the draft's author edits it. The clinician who opened the encounter approves it, and only after sign-off, so it matches the record; from then on the wording never changes and it is what the patient will read (Step 8). A wrong one is withdrawn (kept, hidden from the patient) and a new one drafted. One summary at a time per visit. Migration 0023.

**Hardest problem:** what a first draft may say. A summary built from the record could carry wording meant for clinicians. *Fix:* the draft builder takes only diagnoses, medicines and next steps, never free-text instructions or referral reasons, and a test checks that; the clinician still reads and approves every word.

**Broke, and fixed:** nothing new.

**Finished:** Week 9 Steps 1–6. Step 7 written, awaiting its Codespace run (needs `alembic upgrade head`). Migration head: 0023.

**Pending:** as on 16 Oct.

**Next:** Week 9 Step 8, the patient web experience: sign in with a one-time SMS code, see visits, book a remote slot, do the intake, join the consult and chat, read approved summaries.

---

## 16 Oct 2026 (Fri): Week 8 finished (offline sync and conflict handling); Week 9 started

**Done**
- Week 9 Step 6: **follow-up and referral** (FR-C5). In the encounter, a doctor or nurse plans a follow-up (see again by a date, in person or remote, optional instructions) and writes referrals (to whom, specialty, urgency, reason). Both go through the device outbox and follow the late-entry rule. Front desk gets a "Follow-ups due" box on the queue (next two weeks and overdue; names, dates and kind only, never the instructions) and marks each booked or not needed. Each referral has a printable letter (print or save as PDF) with the patient's details, reason, active allergies, medicines prescribed at that visit and known problems; the app header is hidden when printing. A referral is never edited; whoever wrote it, or the encounter owner, can cancel it (kept, marked cancelled). Migration 0022.
- Week 9 Step 5: **the consult room** (FR-C3, FR-C4). The clinician running a remote visit opens its room from the encounter: a private Jitsi Meet room (long random name, no names or IDs in the link) behind a video adapter (jitsi, fake for tests, none for chat only). Video opens in a new tab at low resolution; "audio only" is the same room with the camera off; text is the built-in chat, which checks for new messages every 5 seconds with a small request. Every switch between video, audio and text is recorded with its reason, and the screen suggests stepping down when the browser reports a weak connection. Chat messages are never edited; opening the chat is in the audit log, the quiet checks are not. Migration 0021. The patient joins from their own page in Step 8.
- Week 9 Step 4: **teleconsult intake** (FR-C2, FR-C6). New `telehealth` module. Before a remote visit, staff (often on the phone) record the reason and ask the 12 danger-sign questions; the patient must have consented to remote care first. No danger sign: the patient joins the remote waiting room (the visit checks in and shows on the queue, marked Remote). A danger sign: the escalation is recorded in the audit log, in-person advice is shown, and the remote visit cannot check in or start. A remote visit can no longer be checked in by a button, nor started, without that intake. Front desk takes the intake but cannot read it back (the reason is health information); clinicians can. Migration 0020.
- Week 9 Step 3: **clinician availability** (FR-C1). Doctors and nurses publish their own weekly hours on a new "My hours" screen: day, Lagos start and end, in person or remote, slot length, branch. Overlapping hours are refused. Free slots are those hours cut into slots, minus anything already booked and minus the past. The booking form now asks "in person or remote" and offers the clinician's free slots this week (a slot books exactly its length); staff can still type another time. Patients booking themselves (Step 8) will be held to free slots. Migration 0019.
- Week 9 Step 2: **triage.** A doctor or nurse sets how urgent a checked-in patient is (emergency, urgent, standard) and ticks danger signs from a fixed list of 12; any danger sign makes it an emergency, on screen and on the server. The queue now shows emergencies first, then urgent, then everyone else in arrival order. Front desk sees the urgency but not the danger signs (clinical). Triaging again adds a new row; the newest counts and the history is kept. Codes only, no free text. Migration 0018. The same danger-sign list will screen teleconsult intake (Step 4).
- Week 9 plan agreed (8 steps): prescriptions, triage, clinician availability, teleconsult booking and intake, consult room (chat + Jitsi video with audio/text fallback), follow-up and referral, clinician-approved summary, patient web experience. Decisions: patients sign in with a one-time SMS code; video through Jitsi Meet room links behind an adapter; medicines typed freely with separate dose, route, frequency and duration boxes.
- Week 9 Step 1: **prescriptions** (FR-R2). Doctors only (new `clinical:prescribe` permission); nurses read them. Written inside an encounter through the device outbox, so drafts work offline (FR-O1) and one written before sign-off is accepted after it, marked late. Stopping or "written by mistake" is a new version, allowed after sign-off; two devices changing one prescription keep both as a conflict for a doctor to settle. Migration 0017.
- Week 8 Step 8: **the conflict screen and the offline chaos test.** A version in conflict shows beside the one in use with "Keep this version" / "Keep the current one" (each asks first); only those allowed see the buttons (vitals: either recorder or the encounter owner; notes: the author; allergies and problems: any clinician), and the server checks again. The chaos test runs 12 seeded scenarios: three devices' queued writes arrive shuffled, re-sent up to three times, after sign-off. Every time: nothing lost, nothing doubled, one audit line per real write, late entries marked, each disagreement ends as one version in use plus one conflict, and after settling exactly one version per chain. README roadmap: W8 ticked. Brief check updated.
- Week 8 Step 7c: **registering patients offline.** With no network the form saves the registration on the device (or offers to, if the network drops mid-send), and the outbox sends it with its own ID and `registered_offline`. The server never refuses it as a possible duplicate (nobody could answer the question offline): it saves it and flags it `needs_review`. Front desk opens "Registrations to review", compares with the possible matches, and decides "Someone new" or "Same person as …". Nothing is merged or deleted: a duplicate points at the original. Every look and decision is in the audit log. Migration 0016.
- Week 8 Step 7b: **the app opens with no network.** A service worker (`public/sw.js`) keeps the app's own files and the pages already opened on this device. Pages are fetched from the network first; if it fails, or takes more than 6 seconds (slow networks), the kept copy is shown, else a plain offline page. It never touches the API, writes, other sites, errors or redirects. Kept pages hold no patient data (screens load that in the browser), only the staff member's name, and are deleted at sign-out.
- Week 8 Step 7a: **offline reads.** A small copy of what the person last read is kept on the device: today's queue and visit list, branches, clinicians, and the encounters opened on this device (current vitals and notes, allergies, problems, and that patient's name and age). Never patient search, other patients, consent or audit. The copy is put back on screen when the app opens, so an encounter opened earlier still shows offline, with a notice that it is the saved copy. It is deleted at sign-out, after 24 hours, and when someone else signs in on the device. The device database moved to version 2 (outbox + reads).
- Week 8 Step 6: **the encounter screen writes through the outbox.** Vitals, allergies, problems and notes (and their corrections) are saved on the device first and sent from there, with the device's time on new vitals and notes. A header badge says "All saved", "N waiting to sync", "Offline", "Sign in again to send N" or "N not saved", and opens the list (refused ones show the server's reason and can be dismissed). The encounter shows what is still on the device and holds sign-off until it is sent. Sign-out is refused while anything is waiting or refused-but-not-dismissed. Each write belongs to the person who made it: after an expired session, someone else signing in on the device never sends it under their name. Opening and signing off an encounter stay online-only.
- Week 8 Step 5: **the device outbox** (frontend, `src/lib/sync/`). A write made on the device is stored in IndexedDB first, then sent oldest-first with its own `Idempotency-Key`, so a re-send after a dropped connection is never recorded twice. No network: stop and keep everything in order. Session ended: keep everything untouched. Refused for good (403/404/409/422): kept, marked failed with the server's reason, and the rest carry on. Only one send runs at a time. Not yet connected to the screens (Step 6).
- Week 8 Step 4: **late offline entries.** Vitals or a note taken on a device that was offline, before the doctor signed off, are accepted when they arrive after sign-off and marked `synced_late` (a "Synced late" badge on the encounter screen). Accepted only if the device time falls between the encounter opening and sign-off; an entry with no device time, or dated after sign-off, is still refused. Notes now keep the device's time (`written_at`) as well as the arrival time. Migration 0015.
- Week 8 Step 3: **conflicting corrections are kept, never refused or overwritten** (FR-O4). If two devices correct the same vitals, note, allergy or problem, the second one is saved with status `conflict`, shown beside the current version, and a clinician chooses which to keep (`POST /vitals|notes|allergies|problems/{id}/resolve` with `keep: this|current`). The one not chosen goes into history; nothing is deleted, and the choice is in the audit log. Who may choose: vitals, whoever recorded either set or the encounter owner; notes, the author only; allergies and problems, any clinician.
- Week 8 Step 1 (written on 15 Oct) confirmed in the Codespace: migration 0013 up and down, backend tests green, 156 frontend tests. A write sent twice with the same `Idempotency-Key` now happens once (the SRS acceptance test: 3 sends, 1 record).
- Week 8 Step 2: every audit line records **which device** it came from (FR-A2). Each browser keeps a random device ID (not a fingerprint), sends it as `X-Device-Id`, the pass-through forwards it only if it is a proper UUID, and the admin audit log shows a Device column.

**Hardest problem: getting the device into every diary line without touching dozens of service calls**
- *Fix:* the device is read once per request into a per-request context variable that the diary reads by itself. A test proves one request's device never leaks into the next, and work done outside a request (the reminder worker) records no device.

**Second hard problem: finding "the current version" a conflict competes with**
- After a conflict is made, the current set may itself be corrected again, so it is no longer the direct child of the version both devices started from.
- *Fix:* follow the `replaces_id` links forward from that starting version, skipping conflicts, until the one current version is found. A test covers a chain of three corrections.
- *Changed on purpose:* three old tests expected "correcting an old version is refused". Offline work makes that rule lose clinical writes, so they now expect a conflict instead; correcting a conflict itself is still refused until it is settled.

**Broke, and fixed**
- *Test clean-up missed the new tables* (prescription, triage, availability, from Week 9 Steps 1–3): after each test the clean-up deletes rows table by table, and a prescription or triage still pointing at an encounter or visit blocks that delete. Fixed in `tests/conftest.py` by clearing the new tables first (plus teleconsult_intake). Lesson: every new table goes into the clean-up list in the same step.
- *A proxy test used a header value with a line break:* real `Headers` objects refuse those before our code runs, so the test would have failed for the wrong reason. Replaced with a plain malformed value.

**Finished:** Week 8 (all green in the Codespace). Week 9 Steps 1–5 green (Step 6 confirmed green on 19 Oct).

**Pending:** as on 15 Oct, plus merging duplicate patients (W11).

**Next:** Week 9 Step 7, the clinician-approved patient summary (FR-R4).

**Pending (new):** merging a duplicate patient's visits into the original record (W11, with the admin screens).

**Known limit:** new vitals carry the device's clock. A device clock more than 5 minutes fast is refused ("in the future"); the reason shows in the sync list.

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
