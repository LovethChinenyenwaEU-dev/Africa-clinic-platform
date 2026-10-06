---
name: clinic-fhir-export-adapters
description: How to build FHIR-aligned export and to integrate external providers (SMS/WhatsApp, payments, video, labs, HMOs) through adapters, queues and retries in the Clinic Platform. Use whenever adding or changing an integration, webhook, payment gateway, notification, video provider, background job, import/export, referral sharing or interoperability feature, and whenever the user mentions FHIR, adapters, Paystack/Flutterwave-style gateways, SMS providers, webhooks, retries, or exporting patient data.
---

# FHIR export and provider adapters

## Adapter pattern
Every external service sits behind an interface owned by our code. Business logic never imports a vendor SDK directly.

```python
class SmsProvider(Protocol):
    def send(self, to: str, body: str, idempotency_key: str) -> SendResult: ...

class PaymentGateway(Protocol):
    def create_charge(self, invoice_id: str, amount: Decimal, ...) -> ChargeRef: ...
    def verify_webhook(self, headers: dict, body: bytes) -> WebhookEvent: ...

class VideoProvider(Protocol):
    def create_room(self, consult_id: str) -> RoomInfo: ...
```

Layout: `backend/app/<domain>/adapters/{interface.py, <vendor>.py, fake.py}`. Always ship a `fake.py` for tests and local development; selecting the provider is configuration.

## Reliability rules
1. Calls to providers run in **background jobs** (Redis queue), not inside request handlers.
2. Jobs are idempotent: pass an idempotency key; store the outcome.
3. Retry with exponential backoff and a maximum; after the limit, mark `failed`, alert, and expose in the admin notification console.
4. Add timeouts and a circuit breaker per provider so one outage does not stall the system.
5. Pass through third-party costs transparently in usage records (SMS count, video minutes).
6. Never put PHI in SMS/WhatsApp bodies beyond what the patient consented to; prefer generic reminders ("You have an appointment tomorrow at 10:00").

## Webhooks
- Verify signatures before processing; reject unsigned or replayed events.
- Process idempotently by event ID: a replayed payment webhook must not double-credit an invoice.
- Respond quickly, then do the work in a job.
- Check the provider's current documentation for signature scheme and event names; do not assume from memory.

## FHIR-aligned export
Map internal models to these resources and keep a versioned export endpoint (e.g. `/api/v1/fhir/...`):

| Internal | FHIR resource |
|---|---|
| patient | Patient |
| staff (clinicians) | Practitioner |
| encounter | Encounter |
| observation (vitals) | Observation |
| lab report | DiagnosticReport |
| prescription | MedicationRequest |
| care plan / follow-up | CarePlan |
| consent | Consent |

Rules:
- Export only data the requester is permitted to see and that consent allows; write an audit event for each export.
- Include provenance (who created, when, version) and preserve prior versions.
- Validate output against the FHIR schema in tests; keep sample fixtures with fake data.
- "FHIR-aligned" means we follow the resource structure; do not claim full conformance unless validated.
- Version the API; do not break existing consumers.

## Tests required
- Fake adapter used in unit tests; no network calls in CI
- Retry then fail path produces a visible failed state
- Replayed webhook has no second effect
- Export for a patient contains expected resources and omits other tenants' data
- Export without permission or consent is denied and audited
