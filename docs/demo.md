# Demo script

Week 12. A 10 to 12 minute walk through AfriPeak Health on the live site, one clinic day
from the front desk to the money, then what the owner sees. **Fake people only.**

- Landing page: https://afripeak-landing.onrender.com
- Clinic app: https://afripeak-web.onrender.com/login
- API health: https://afripeak-api.onrender.com/health

## Before the demo (30 minutes ahead)

1. **Wake the services.** Free services sleep after 15 minutes. Open the three addresses above
   and wait until each loads (about a minute each). Keep a tab on each.
2. **Logins.** The admin from `create-clinic`, and, added on the Staff screen with made-up
   names: a front desk person, a nurse, a doctor, and a billing person. Use a different
   browser profile (or a private window) per person so you can switch without signing out.
   Admin and billing need the authenticator app on your phone.
3. **Set-up done by the admin:** a branch (Settings), consent wording for every purpose
   (Settings), prices for "Consultation" and "Malaria test" (Prices), the doctor's and
   nurse's weekly hours (they set these under My hours).
4. **One patient ready**, registered earlier, with treatment consent, so the walk-through can
   also show a returning patient.
5. Run `bash scripts/backup.sh` so the demo can be reset by restoring if needed.

## The walk-through

| # | Who | Show | Say |
|---|---|---|---|
| 1 | (visitor) | The landing page | The problem: separate tools that break when the network does. |
| 2 | Front desk | **Patients > Register**: a new patient with a phone number | Duplicate warning if the same name and birth date, or phone, exist. |
| 3 | Front desk | The patient page: **Consent** for treatment and reminders | Consent points at the exact wording version the patient saw. |
| 4 | Front desk | **Today's queue**: a walk-in, then check in the booked patient | The queue is the day at a glance. |
| 5 | Nurse | Triage with a danger sign | The patient jumps to the top as an emergency. |
| 6 | Doctor | Start the consultation: vitals, an allergy, a diagnosis with an ICD-10 code (B54), a note, a prescription | Nothing is ever overwritten: changes are new versions. |
| 7 | Doctor | Close the encounter; approve the patient summary | Only a clinician-approved summary ever reaches the patient. |
| 8 | Doctor | Patient page: **Export the record (FHIR)**, reason "patient asked" | An open standard another clinic's system can read; the reason goes in the audit log. |
| 9 | Front desk | **Billing**: invoice the visit, take a cash payment, open the receipt | Numbered invoices and receipts; refunds need a second person. |
| 10 | Billing | **Takings** for today; download the CSV | What should be in the cash drawer, and what looks unusual. |
| 11 | Admin | **Dashboard**: last 7 days | Waits, no-shows, completion, sync problems, money, who opened records. Counts only. |
| 12 | Admin | **Audit log**: filter by the patient | Every read and change, by whom, from which device. Reads marked "Look". |
| 13 | Admin | **Staff**: a person's Devices; sign one out | A lost phone stops working at once. |
| 14 | Admin | **Reminders** | What the SMS worker did and why anything failed. |

### Offline (optional, 2 minutes)

As the front desk, in the browser's developer tools (Network > Offline): register a patient.
The top bar shows it waiting on the device. Go back online: it is sent, once, in order. Say:
clinics lose the network; nothing typed is lost, and nothing is sent twice.

## Questions to expect

- **Is real patient data in it?** No. A clinical-safety review, a privacy impact assessment
  and legal review come first (README).
- **Where is the data?** One PostgreSQL database in Render's Frankfurt region; each clinic
  walled off by row-level security in the database itself; authenticator secrets encrypted
  with a key kept outside it; backups restored in a timed drill.
- **What if it is breached?** `docs/runbook.md`.

## Known limits of the live demo

- Free services sleep; the first click after a pause takes about a minute.
- No SMS is really sent (`SMS_PROVIDER=none`), so the patient's SMS sign-in cannot be shown
  live; show it locally with `docker compose` (the code appears in development).
- The free database is deleted 30 days after it was made (made 1 November 2026): restore the
  latest backup into a new one before then, or upgrade.
- The landing page has no link to the clinic app yet (an open landing-page point).
