# Build log

One entry per working day, newest first. Each entry says what was done, the hardest
problem and how it was solved, what broke and how it was fixed, what is finished, what is
pending, and what comes next. Test counts are from the Codespace (backend: `pytest`,
frontend: `npm test`).

Roadmap: [README](./README.md#roadmap-12-week-mvp) · Brief: [docs/product-brief.md](./docs/product-brief.md) · Brief check: [docs/brief-alignment.md](./docs/brief-alignment.md)

---

## 1 Nov 2026 (Sun): Week 11 Step 3, the second factor (backend and screens)

**Done**
- Week 11 Step 2 (row-level security) and the AfriPeak design confirmed green on CI and in the Codespace. The font packages had never been committed: added, which also stopped the service worker showing an old saved sign-in page.
- Week 11 Step 3a: **admins and billing sign in with an authenticator app (FR-T4).** The right password gives them a 5-minute challenge instead of a token (everyone else still gets their token straight away, same answer as before). First time: a secret to add to the app (text and an otpauth:// link), proved by a first code, then 10 one-time backup codes shown once. After that: the app's code or a backup code. TOTP written with the standard library and tested against the RFC 4226 and RFC 6238 examples. One step of clock drift allowed; no code works twice; five wrong codes lock sign-in for 15 minutes. An admin resets a lost phone for someone else, never for themselves. The challenge token opens nothing else (staff and patient doors refuse it). Backup codes are stored as keyed hashes; the secret as text until the W12 key manager. New tables behind the row-level security wall. Migration 0033.

**Hardest problem:** keeping 900 tests that sign in admins working. *Fix:* the second factor sits on the login door (start_sign_in); the plain login() stays for tests and scripts only, and its docstring says never to expose it.

**Finished:** Step 3a green on CI; Step 3b awaiting the Codespace run. Migration head: 0033.

- Week 11 Step 3b: **the sign-in screens for the second factor.** After the password, admins and billing see either the code step (the app's code, or a backup code) or, the first time, the set-up: a button shows their key (grouped in fours, and a link that opens the app on a phone), they type the app's first code, then see their 10 backup codes once and must tick "I have kept these codes" to continue. The challenge stays in its own 5-minute httpOnly cookie, so the page's JavaScript never holds it; a new route `/api/session/mfa` swaps it for the normal session cookie. Clear messages for a wrong code, the 15-minute lock, and an expired step (with "Sign in again").

**Next:** Week 11 Step 4: signing out one device (instead of all of a person's sessions).

---

## 30 Oct 2026 (Fri): the AfriPeak Health design; Week 11 Step 2 (row-level security)

**Done**
- The user's own landing page design (AfriPeak Health) is now the public page. It is kept **exactly as designed** in `landing/`, its own small Next.js app (Next 14, Tailwind 3, DaisyUI 4), because putting it inside the clinic app (Next 16, Tailwind 4, DaisyUI 5 with a `d-` prefix) would have changed its buttons, cards and form fields and let its global CSS restyle the staff screens. It runs on port 3001 (`docker compose` service `landing`), and CI builds it in its own job. The clinic app's `/welcome` and the sign-in page's links now go to it (`LANDING_URL`). The earlier Lafiya page (`frontend/src/features/site`) is kept but no longer shown.
- The landing page calls no backend endpoint. Points where its wording or links differ from what the backend does were listed for the user (no changes made to the design).

- **The clinic app now wears the AfriPeak Health design** (as the user asked): the landing page's colours (deep green, teal, soft green, paper background), fonts (Poppins headings, Roboto text, Raleway menu, served by Fontsource), 8px buttons that lift and turn teal, 16px cards with a soft green shadow, form fields, the brand mark and small capitals, and the deep-green top bar over a white sticky header. Done at the design-system level (tokens, base classes, header, logo), so every staff and patient screen changed at once; page titles say AfriPeak Health. The landing page itself was not touched.
- Week 11 Step 2: **row-level security (brief D2).** A role `clinic_app` that owns no table, and a `tenant_wall` policy on every table with a tenant_id. Once a request knows who is signed in (staff or patient), each transaction runs `SET LOCAL ROLE clinic_app` with `app.tenant_id` set, so a query that forgets its clinic filter finds nothing and nothing can be written into another clinic. Work with nobody signed in (sign-in, SMS sign-in, webhook, worker) keeps the owner role. Settings are transaction-local, so pooled connections never carry a wall over. Outside the wall on purpose: `staff` and the audit chain counter. All API tests now run behind the wall. Migration 0032.

**Hardest problem:** PostgreSQL never applies row-level security to the table owner or a superuser, which is what the app connects as. *Fix:* a separate role without ownership, switched to with SET LOCAL ROLE only for signed-in work. *Lesson:* check who the rule applies to before trusting it.

**Pending:** the user's decisions on the landing page points; MFA next.

**Next:** Week 11 Step 3: MFA (authenticator app) for admins and billing.

---

## 26 Oct 2026 (Mon): Week 11 started: a tamper-evident audit log

**Done**
- Week 10 Step 7b confirmed green on CI.
- Week 11 decisions: MFA with an **authenticator app** (TOTP, plus backup codes) for **admins and billing**; attachments **after the MVP**. Order: tamper-evident audit, database row-level security, MFA, one-device sign-out, dashboards, FHIR-aligned export, admin screens and the notification console.
- Week 11 Step 1: **the audit log is tamper-evident (brief D3).** Each clinic's audit lines form a chain: every line stores its number, the previous line's hash and its own SHA-256 hash over all its fields. A database trigger writes them, so no code path can skip them or choose them (a test tries). A per-clinic chain head is locked while a line is numbered. One SQL function defines the hash for both writing and checking. Existing lines were chained by the migration, oldest first. `GET /audit/chain` (admins) recomputes the chain and names the first line that was changed, removed or slipped in, and gives the head (number and hash) to write down. Tests switch the append-only trigger off the way a database owner could, tamper, and see the check catch it. Migration 0031.

**Broke, and fixed**
- *The frontend build failed on CI with "Can't resolve '@vercel/turbopack-next/internal/font/google/font'"* for all three fonts. Cause: `next/font/google` downloads the fonts from Google during the build, and that download failed on the CI runner. Fix: the fonts are now Fontsource npm packages, served by our own app, so the build needs no network and no browser contacts Google (better for privacy and for offline use too).

**Hardest problem:** two lines added at the same moment must not get the same number, and the app must not be trusted to number them. *Fix:* the trigger locks the clinic's chain head row (SELECT ... FOR UPDATE) for the rest of the transaction. *Lesson:* integrity rules belong in the database when the threat is someone going around the app.

**Finished:** Step 1 awaiting the Codespace run (`alembic upgrade head`). Migration head: 0031.

**Pending:** frontend redesign with the Lafiya components (after Week 11); anchoring the chain head outside the database (W12 backups).

**Next:** Week 11 Step 2: PostgreSQL row-level security as a second wall between clinics (brief D2).

---

## 25 Oct 2026 (Sun): Week 10 finished: the daily takings and the billing screens

**Done**
- Step 5 confirmed green after one test fix: the "check now" test kept a row object and read its status after a later check had changed it (one object per row in a session). The payment code was right.
- Week 10 Step 6: **the daily takings (reconciliation).** For one Lagos day (midnight to midnight Lagos time): money in by method and by the person who took it, refunds approved that day, the net per method (net cash is what should be in the drawer), and how many invoices were issued for how much. Things to look at: invoices paid beyond their total and not yet given back; refunds waiting for an admin; online payments that failed; and unusual refunds asked that day (the whole payment back, asked by the person who took the payment, or one person asking for more than three). A CSV export of the day's payments and refunds with numbers and amounts but no patient names, for an accountant (sent inside JSON, because the staff pass-through only carries JSON). Admins and billing only (`takings:read`); every view and export is in the audit log. No new tables.
- Week 10 Step 7a: **the billing screens, part one.** Menu: Billing (front desk, billing) and Prices (admins change, front desk and billing read). Billing: find the patient, see their recent visits with each one's invoice and what is owed, and "Bill this visit". The invoice: services from the price list (with how many), remove a line, issue or void with a reason; then take cash or a transfer (never more than is owed), make a Paystack link and "Check now", ask for a refund on a payment, and see refunds and their status. A printable receipt with its check code. Money is typed in naira and turned into kobo by reading the text, never with floating point. New backend door `GET /billing/patients/{id}/visits` (billing staff cannot read the queue). The menu now marks only the closest item (/billing/prices is "Prices", not "Billing" too).
- Week 10 Step 7b: **refund decisions and the daily takings screens.** Refunds (admins): waiting, approved and rejected lists with who asked and when; approve (optional note) or reject (note needed); a refund the admin asked for themselves shows "another admin must decide it". Takings (admins, billing): pick a Lagos day; money in, given back, net, and cash in the drawer; invoices issued; the things to look at; by method and by person; "Download CSV". **Week 10 is complete.**

**Hardest problem:** what "a day" is. A payment at 23:30 UTC on Monday is 00:30 on Tuesday in Lagos. *Fix:* reuse the scheduling day bounds (Lagos midnight to midnight), and a test puts a payment just after midnight to prove it lands on Tuesday.

**Finished:** Steps 6 and 7a green on CI; 7b awaiting the Codespace run. Week 10 done (README ticked, brief check: billing done). Migration head: 0030.

**Pending:** to try Paystack itself: a test secret key in the Codespace `.env`, `PAYMENT_GATEWAY=paystack`, and the API port public for the webhook.

**Next:** go back to the frontend design (restyle the staff and patient screens with the Lafiya components), then Week 11 (FHIR-style export, dashboards, security hardening).

---

## 23 Oct 2026 (Fri): CI green again; test dates fixed; Week 10 Steps 1 to 5 (prices, invoices, payments, refunds, Paystack)

**Done**
- **Test dates no longer expire.** New `backend/tests/dates.py`: `MONDAY` is always a Monday 8 to 14 days ahead, `FRIDAY_BEFORE` three days before it. The scheduling helpers, booking, availability, day list, demo data and patient portal tests count from it instead of 2 Nov 2026. Tests of pure functions (reminder wording, status moves, chart rules, audit filters) keep fixed dates on purpose: no clock is involved.
- Week 10 decisions: **Paystack** behind an adapter; front desk and billing take payments and ask for refunds, **only an admin approves a refund, never their own request**; **naira only, stored as whole kobo**; invoices are **built per visit from the price list**, editable as a draft, frozen once issued.
- Week 10 Step 1: **the price list.** Admins add services (name, optional code, price in kobo), change them, retire them (never deleted) and bring them back. No two active services of a clinic share a name, whatever the capitals (checked in code and by a unique index). Front desk, nurses, doctors and billing read the list. Every addition and change is in the audit log. New capabilities `price:read` and `price:write`. Migration 0026.
- **CI repaired.** GitHub had not run since Week 8, and the first run (#73) was red. Three committed files were broken while the Codespace had good copies: `ReviewStatus` was missing from `patients/models.py`, a line was split in `RegisterPatientForm.tsx` (both from the W8 step 7c edit), and the frontend packages were never committed. Also fixed: the session cookie's Secure flag was decided at import time (W9 8a), portal tests depended on the container's environment, and an intake test was a coin toss between two equal timestamps. Backend 882 and frontend 295 tests green on CI.
- Week 10 Step 2: **invoices.** Front desk or billing starts the invoice for a visit (one live invoice per visit; a cancelled visit is not billed) and adds services from the price list with a quantity; each line copies the name and price, so a later price change never changes it. A draft can lose lines or be voided with a reason. Issuing gives the clinic's next number (`INV-000001`, per clinic, from a locked counter so two at once never share one) and freezes it. Admins read invoices; nurses and doctors do not handle money. Every view and change is in the audit log with the patient. Migration 0027.
- Week 10 Step 3: **payments and receipts.** Front desk or billing records cash, or a bank transfer with the bank's reference, against an issued invoice. Never more than is still owed: the invoice is locked while the balance is worked out. One transfer reference is recorded once per clinic (whatever the capitals), so a transfer cannot be counted twice. Each payment gets the clinic's next receipt number (`RCT-000001`). Payments are never edited or deleted (a refund will put mistakes right). Invoices now show paid, still owed and a status: unpaid, part paid or paid, worked out from the payments, never stored. A receipt shows the clinic, patient, invoice, amount, paid so far, balance, who took it, and a 10-character check code made with the server's secret. Admins can read receipts but not take money. Migration 0028.
- Week 10 Step 4: **refunds with two people (FR-B3).** Front desk or billing asks for money back from one payment (amount, cash or transfer, and why). Only an admin decides, and never a request they made: the service refuses it and a database check refuses it again. Admins cannot ask at all. Requests still waiting count against the payment, so two requests can never give back more than was paid; a rejection frees the amount. An approval gets the clinic's next refund number (`RFD-000001`). An approved refund is for something not given or overcharged, so it lowers what was paid and what is owed alike: the invoice shows refunded, and a full refund shows the status "refunded". Admins have a list of refunds waiting. Migration 0029.
- Week 10 Step 5: **Paystack behind an adapter (FR-B4).** `billing/gateway.py` holds the only Paystack code (initialize, verify, webhook signature); a fake gateway for tests and "none" (cash and transfer only, the default). Front desk or billing makes a payment link for what is owed; the gateway gets the amount and the invoice number only, never names or health details. Paystack's webhook is public but must carry a valid HMAC-SHA512 signature, and it is only a hint: the payment is counted after Paystack's own verify agrees on the amount and currency. Completing locks the link's row, so repeated webhooks or "check now" record exactly one payment; the database backs this up (one payment per link, one gateway reference per clinic). Staff cannot type in an online payment or refund to a card. Money that arrives after a bill was settled is still recorded and the invoice shows "overpaid" with the credit owed back. Migration 0030.

**Hardest problem:** "it passes on my machine". A green Codespace only proves the files in the Codespace work; three broken files had been committed for a week. *Fix:* repair them, and read the Actions page after every push. *Lesson:* CI is the only check of what is actually committed.

**Also hard:** money in a web form. A float turns 0.1 + 0.2 into 0.30000000000000004, and `True` is an integer in Python. *Fix:* the API takes whole kobo only (`StrictInt`), the service refuses booleans and fractions, and the column is a BIGINT. *Lesson:* decide the unit of money before the first table.

**Finished:** CI fixes, test dates, Steps 1 to 5 (green on CI after a test fix on 25 Oct). Migration head: 0030.

**Pending:** to try Paystack itself (not needed for the tests): a Paystack test secret key in the Codespace `.env`, `PAYMENT_GATEWAY=paystack`, and the API port made public so Paystack can reach the webhook.

**Next:** Week 10 Step 6: the daily takings (reconciliation): money in and out by method and person, overpaid invoices, unusual refunds.

---

## 22 Oct 2026 (Thu): the Lafiya brand and the public site

**Done**
- Brand: the product is now **Lafiya** (Hausa for health). Logo (a doorway with a person in it), colours (clinic green, indigo for remote care, red, amber and green only for status) and fonts (Atkinson Hyperlegible for reading, Bricolage Grotesque for headings, IBM Plex Mono for numbers). Mockups of the brand sheet, the staff queue and the doctor's encounter on the design canvas.
- Design system in the frontend: DaisyUI 5 with a `d-` prefix (so it never clashes with our `.card`, `.badge`, `.button`) and a single `lafiya` theme; shadcn/ui Button and Accordion coloured with our tokens; `cn()` helper; fonts through `next/font`. Existing screens pick up the new colours and fonts without code changes; the staff header and sign-in page show the logo; page titles say Lafiya.
- Public page `/welcome`, laid out after the reference design the user supplied: header with a phone menu, hero, highlights, why Lafiya, six features, how a visit flows, demo request, roles, questions, contact and footer. Photos are Unsplash placeholders. The demo form says plainly that nothing is sent yet.

**Hardest problem:** three sets of colour names in one app. DaisyUI, shadcn/ui and our own tokens all want `primary` or `accent`. *Fix:* DaisyUI is prefixed and its `accent` is set to the same green as ours; shadcn components are copied in and use our token classes instead of their own colour variables. *Lesson:* pick one source of colours and make the others point at it.

**Finished:** brand and `/welcome`, awaiting the Codespace run (new npm packages).

**Pending:** the demo form is not connected; real photos and contact details; restyling the staff and patient screens with the new components; the three phone mockups.

**Next:** move the fixed test dates (before 2 Nov), then Week 10: billing with one payment gateway, services and prices.

---

## 21 Oct 2026 (Wed): Week 9 finished: the patient web pages (Steps 8a and 8b)

**Done**
- Week 9 Step 8b: **patients use remote care themselves.** On their own page a patient reads the clinic's wording for remote care and agrees; picks a free remote slot (one booked from the page at a time; only real free slots; a double tap books once); answers the intake with the same 12 danger-sign questions staff ask (a danger sign shows the in-person advice and stops the remote visit); waits in the remote waiting room; and, once the clinician opens the room, joins by video or audio and chats. Another patient's visit answers like one that does not exist. Consent and booking can now be recorded with no staff member: `recorded_via` and `booked_via` say "patient_portal". Every step is in the audit log with the patient as the actor. Migration 0025. README: W9 ticked. Brief check updated.
- Week 9 Step 7 (patient summary) confirmed green in the Codespace.
- Week 9 Step 8a: **patients sign in and see their own record.** Each clinic has a patient link (`/patient/<clinic ID>`, shown on the staff home page for front desk to share). The patient types their phone number and date of birth; if both match exactly one patient of that clinic, a 6-digit code goes by SMS. The answer is the same either way, so nobody can find out who is registered. The code lasts 10 minutes, works once, allows 5 tries, and at most 3 are sent per phone every 15 minutes; only a keyed hash is stored. In development (SMS off) the code is shown on screen. The patient then sees their upcoming and past visits and the summaries their clinician approved (never drafts or withdrawn ones). Patients have their own token (marked as a patient token) and their own httpOnly cookie and pass-through: a patient token is refused on staff doors and a staff token on patient doors. Every patient action is in the audit log with the patient as the actor; the admin audit log shows it as "The patient, on their own page". Migration 0024.

**Hardest problem:** families sharing one phone. A code to "whoever owns this number" would open a sibling's or a parent's record. *Fix:* phone **and** date of birth must match exactly one patient before any code is sent; a test signs a child in on the mother's phone.

**Broke, and fixed**
- *Shell commands with an apostrophe in the text failed before running* (nothing was written): files with such text are now written with the editor instead.

**Finished:** Week 9 (Steps 1–8a green; 8b awaiting its Codespace run, needs `alembic upgrade head`). Migration head: 0025.

**Pending:** as on 16 Oct. A real SMS provider is now needed for patient sign-in outside development. Patient self-cancel and caregiver access (FR-P4) not built. **Urgent:** many tests are fixed at 2 Nov 2026 and will fail after that date; the 8b tests already count from today.

**Next:** move the fixed test dates (before 2 Nov), then Week 10: billing with one payment gateway, services and prices.

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
