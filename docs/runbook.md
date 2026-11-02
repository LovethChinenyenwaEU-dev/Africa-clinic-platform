# Privacy and incident runbook

Week 12. What to do when patient data may have been seen, changed or lost by someone who
should not have it, and how long each kind of data is kept.

This is a working guide for the pilot, not legal advice. The deadlines below are from the
Nigeria Data Protection Act 2023 as we understand it; the clinic's lawyer and Data
Protection Officer have the final word, and must review this before real patient data is
used.

## Who does what

| Role | Who (fill in before the pilot) | Does |
|---|---|---|
| Incident lead | the clinic's owner or medical director | decides, keeps the timeline, signs off notices |
| Technical lead | whoever runs the deployment | contains, investigates, restores |
| Data Protection Officer (DPO) | named by the clinic | judges the risk, writes to the regulator and patients |

Keep a written timeline from the first minute: what was noticed, when, by whom, and every
step taken. It is needed for the regulator and for learning afterwards.

## What counts as an incident

Report it to the incident lead at once if any of these happen or are suspected:

- a phone, laptop or tablet that was signed in is lost or stolen;
- a staff password, authenticator app or backup codes are shared, seen or lost;
- someone opened records they had no reason to (the audit log shows "Look" reads);
- a backup file, export (FHIR file, takings CSV) or screenshot with patient data went
  somewhere it should not (email, chat, a public place);
- the audit chain check reports a broken chain;
- secrets (database address, `SECRET_KEY`, `DATA_ENCRYPTION_KEYS`, Paystack keys) were
  exposed;
- the site was changed, defaced, or data was lost.

## The first hour: contain

Do what fits; the order matters.

1. **A lost or stolen device:** an admin opens **Staff**, the person's **Devices**, and signs
   that device out. It stops working at once. If their authenticator phone is lost too,
   **Reset authenticator app**.
2. **A staff account misused, or a person leaves suddenly:** **Staff > Switch off**. They are
   signed out everywhere at once; their records and audit lines stay.
3. **A secret exposed:**
   - database password: in Render, change the database credentials, check `afripeak-api`
     comes back Live;
   - `SECRET_KEY`: replace it in Render (afripeak-api > Environment). Everybody is signed
     out, which is what you want;
   - `DATA_ENCRYPTION_KEYS`: put a new key **first** and keep the old one after it
     (`new,old`), never just replace it (see `docs/deploy-render.md`);
   - Paystack keys: roll them in the Paystack dashboard, then update Render.
4. **Something is actively going wrong (data being taken or changed):** in Render, suspend
   `afripeak-web` so nobody can use the app; the API and database keep running for the
   investigation.
5. **Take a backup now** (`bash scripts/backup.sh`) and keep it apart: it is evidence of the
   state at the time.

## The first day: investigate

- **Audit log** (admins): filter by the staff member, the patient or the days. It shows every
  read and change of patient data, from which device. Reads are marked "Look".
- **Audit chain check:** confirms the log itself was not edited. Signed in as an admin,
  open `https://afripeak-web.onrender.com/api/backend/audit/chain` in the same browser
  (the API route `GET /api/v1/audit/chain`). It answers whether the chain is intact, where
  it first breaks if not, and the head. Compare the head with the latest backup's
  `.heads.json`: the line number should be at or after it. For a full proof, run the
  restore drill on that backup (`docs/backup-restore.md`).
- **Dashboard > Who opened patient records**: unusual counts by one person stand out.
- **Signed-in devices**: Staff > Devices shows where each person is signed in now.
- Write down: which patients, what kind of data (identity, clinical, payment), how many
  people, since when, and whether it is contained.

## Notify

Under the NDPA 2023, as we understand it (confirm with the DPO and lawyer):

- **The regulator:** a breach likely to put people's rights and freedoms at risk is reported
  to the **Nigeria Data Protection Commission (NDPC) within 72 hours** of becoming aware of
  it. If not everything is known yet, report what is known and send the rest later.
- **The patients affected:** when the risk to them is high, tell them **without undue
  delay**, in plain words: what happened, what data, what we have done, what they can do,
  and who to contact.
- Record every decision, including a decision **not** to notify and why.

Health data is sensitive personal data: assume a breach of clinical notes, diagnoses or
prescriptions is high risk unless the DPO decides otherwise.

## Afterwards

Within two weeks: a short review with the timeline, the cause, what worked, what did not,
and the changes to make (each with an owner and a date). No blame: the aim is that it
cannot happen the same way twice.

## How long data is kept

| Data | Kept | How |
|---|---|---|
| Patient records, visits, consents, invoices | until the clinic's retention policy says otherwise | never deleted by the app; mistakes are marked, versions kept |
| Audit log | always | append-only and hash-chained: the database refuses changes and deletes |
| Remembered write answers (offline sync) | 1 day | deleted by the worker (`purge_old_records`) |
| Patient SMS sign-in codes | 10 minutes, used once | expire; only a keyed hash is stored |
| Staff sign-ins (devices) | 30 minutes each | end on sign-out, switch-off or expiry |
| Offline copies on a device | until sign-out, at most 24 hours | wiped by the app |
| Backups | the last four weekly backups | delete older ones (`docs/backup-restore.md`) |
| Exported files (FHIR, CSV) | as short as possible | delete from the device after sending |
| Register interest requests (landing page) | 1 year | deleted by the worker (`purge_old_interest`); read with `python -m app.cli list-interest` |

Configurable retention (deleting records after N years, as a clinic's policy or the law may
require) is not built yet: it needs the clinic's policy and legal advice first.
