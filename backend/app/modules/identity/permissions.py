from enum import StrEnum

from app.modules.identity.models import Role


class Capability(StrEnum):
    """One thing a person may be allowed to do."""

    BRANCH_READ = "branch:read"
    BRANCH_WRITE = "branch:write"
    STAFF_READ = "staff:read"
    STAFF_MANAGE = "staff:manage"
    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    CONSENT_TEXT_READ = "consent_text:read"
    CONSENT_TEXT_WRITE = "consent_text:write"
    CONSENT_READ = "consent:read"
    CONSENT_WRITE = "consent:write"
    AUDIT_READ = "audit:read"
    APPOINTMENT_READ = "appointment:read"
    APPOINTMENT_WRITE = "appointment:write"
    APPOINTMENT_CONSULT = "appointment:consult"
    CLINICAL_READ = "clinical:read"
    CLINICAL_WRITE = "clinical:write"
    PRESCRIBE = "clinical:prescribe"  # write and change prescriptions: doctors only
    PRICE_READ = "price:read"  # the price list: no patient data
    PRICE_WRITE = "price:write"  # add and change prices: admins only
    INVOICE_READ = "invoice:read"  # who was billed for what: personal data
    INVOICE_WRITE = "invoice:write"  # start, change, issue and void invoices
    PAYMENT_RECORD = "payment:record"  # take cash or record a bank transfer


_EVERYONE = frozenset({Capability.BRANCH_READ})
_ADMIN_ONLY = frozenset(
    {
        Capability.BRANCH_WRITE,
        Capability.STAFF_READ,
        Capability.STAFF_MANAGE,
        Capability.CONSENT_TEXT_WRITE,
        Capability.AUDIT_READ,
    }
)
_WORDING_READERS = frozenset({Capability.CONSENT_TEXT_READ})
_PATIENT_READERS = frozenset({Capability.PATIENT_READ})
_PATIENT_REGISTRARS = _PATIENT_READERS | {Capability.PATIENT_WRITE}
_CONSENT_RECORDERS = frozenset({Capability.CONSENT_READ, Capability.CONSENT_WRITE})
_SCHEDULERS = frozenset({Capability.APPOINTMENT_READ, Capability.APPOINTMENT_WRITE})
# Encounters, vitals, allergies, problems and notes: doctors and nurses only.
_CLINICIANS = frozenset(
    {Capability.APPOINTMENT_CONSULT, Capability.CLINICAL_READ, Capability.CLINICAL_WRITE}
)
# The price list holds no patient data: everyone who books or bills reads it.
_PRICE_READERS = frozenset({Capability.PRICE_READ})
_FRONT_LINE = (
    _EVERYONE
    | _PATIENT_REGISTRARS
    | _CONSENT_RECORDERS
    | _WORDING_READERS
    | _SCHEDULERS
    | _PRICE_READERS
)
# Prescribing is a medical act: doctors only. Nurses still read prescriptions (clinical:read).
_PRESCRIBERS = frozenset({Capability.PRESCRIBE})
# Setting prices is the owner's decision: admins only.
_PRICE_SETTERS = _PRICE_READERS | {Capability.PRICE_WRITE}
# Invoices: front desk and billing make them; admins read them (they approve refunds).
# Nurses and doctors do not handle money.
_INVOICE_READERS = frozenset({Capability.INVOICE_READ})
_BILLERS = _INVOICE_READERS | {Capability.INVOICE_WRITE, Capability.PAYMENT_RECORD}

# The one table that says who may do what. Change a rule here, nowhere else.
ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ADMIN: _EVERYONE | _ADMIN_ONLY | _WORDING_READERS | _PRICE_SETTERS | _INVOICE_READERS,
    Role.FRONT_DESK: _FRONT_LINE | _BILLERS,
    Role.NURSE: _FRONT_LINE | _CLINICIANS,
    Role.DOCTOR: _FRONT_LINE | _CLINICIANS | _PRESCRIBERS,
    Role.BILLING: _EVERYONE | _PATIENT_READERS | _PRICE_READERS | _BILLERS,
}

def capabilities_for(role: str) -> frozenset[Capability]:
    """Everything this role may do. Unknown or forgotten roles get nothing."""
    try:
        return ROLE_CAPABILITIES[Role(role)]
    except (ValueError, KeyError):
        return frozenset()


def role_has(role: str, capability: Capability) -> bool:
    return capability in capabilities_for(role)