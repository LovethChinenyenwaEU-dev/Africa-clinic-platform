# ADR-0003: Patient data rules (diary, consent, who sees what)

- **Status:** Accepted
- **Date:** 2026-10-12

## Context
Patient records, consent and an access diary are the first features that hold personal health information.

## Decision
- **Every read or write of patient information writes a diary line in the same transaction.** The action and its line either both happen or neither does.
- **The diary is append-only,** enforced by a database trigger as well as by our code. It holds IDs and codes only: never names, phones, notes or search words.
- **Reading the diary is also logged.** Only admins may read it.
- **Admins have no patient access by default.** They manage the clinic and supervise through the diary. Front desk, nurse and doctor register and read patients and record consent. Billing can read patients.
- **Duplicate patients produce a 409 warning with IDs and reasons only.** A human confirms before a second record is created.
- **Consent points at an exact, versioned wording.** Wording is never edited: a new wording is a new version. Revoking stamps the record; it never deletes.
- **Another clinic's data answers 404,** identical to a missing ID.
- **Phone numbers are stored in one standard form** so duplicates can be found.

## Consequences
- Every new patient-data feature needs a diary action, a capability, a clinic-wall test and a "nothing saved on failure" test.
- Admins need a patient ID from clinic staff to investigate a specific patient. That is deliberate.
- Legal questions (consent for minors, emergencies, cross-clinic sharing) stay with the clinic's lawyer.