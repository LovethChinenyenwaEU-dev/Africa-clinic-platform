"""Vital signs: record, correct and read.

The ranges only catch typing mistakes (a temperature of 370, an SpO2 of 150).
They are wide on purpose and are NOT clinical judgement: an abnormal but
possible value is always accepted.
"""
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, col

from app.core.tenant_scope import get_in_tenant, tenant_select
from app.modules.audit.service import AuditAction, add_audit_event
from app.modules.records.models import Encounter, VitalSigns
from app.modules.records.service import (
    EncounterNotFoundError,
    EncounterNotOpenError,
    NotCurrentVersionError,
    _require_clinician,
)
from app.modules.records.statuses import EncounterStatus, VersionStatus


class InvalidVitalsError(ValueError):
    """The readings are missing, impossible, or too precise."""


class VitalsNotFoundError(Exception):
    """No vitals with this ID in this clinic."""


class NotVitalsAuthorError(Exception):
    """Only whoever recorded the vitals, or the encounter's owner, may correct them."""


@dataclass(frozen=True)
class VitalReadings:
    systolic_mmhg: int | None = None
    diastolic_mmhg: int | None = None
    pulse_bpm: int | None = None
    respiratory_rate: int | None = None
    spo2_pct: int | None = None
    temperature_c: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None


# A device clock may run a little ahead of the server.
CLOCK_SKEW = timedelta(minutes=5)

# (lowest, highest, decimal places allowed). Wide human limits, newborn to adult.
RANGES: dict[str, tuple[Decimal, Decimal, int]] = {
    "systolic_mmhg": (Decimal(40), Decimal(300), 0),
    "diastolic_mmhg": (Decimal(20), Decimal(200), 0),
    "pulse_bpm": (Decimal(20), Decimal(250), 0),
    "respiratory_rate": (Decimal(4), Decimal(80), 0),
    "spo2_pct": (Decimal(50), Decimal(100), 0),
    "temperature_c": (Decimal(25), Decimal(45), 1),
    "weight_kg": (Decimal("0.3"), Decimal(400), 2),
    "height_cm": (Decimal(20), Decimal(250), 1),
}

# How staff see each reading in a message, never the internal field name.
READING_NAMES: dict[str, str] = {
    "systolic_mmhg": "Systolic blood pressure (mmHg)",
    "diastolic_mmhg": "Diastolic blood pressure (mmHg)",
    "pulse_bpm": "Pulse (per minute)",
    "respiratory_rate": "Breathing rate (per minute)",
    "spo2_pct": "SpO2 (%)",
    "temperature_c": "Temperature (°C)",
    "weight_kg": "Weight (kg)",
    "height_cm": "Height (cm)",
}


def check_readings(readings: VitalReadings) -> None:
    """Raise InvalidVitalsError if anything was clearly mistyped."""
    values = asdict(readings)
    if all(value is None for value in values.values()):
        raise InvalidVitalsError("Enter at least one reading.")

    for name, value in values.items():
        if value is None:
            continue
        lowest, highest, places = RANGES[name]
        number = Decimal(value).normalize()  # 37.50 counts as 37.5
        label = READING_NAMES[name]
        if not lowest <= number <= highest:
            raise InvalidVitalsError(f"{label} must be between {lowest} and {highest}.")
        if -number.as_tuple().exponent > places:
            raise InvalidVitalsError(f"{label} allows at most {places} decimal places.")

    systolic, diastolic = readings.systolic_mmhg, readings.diastolic_mmhg
    if (systolic is None) != (diastolic is None):
        raise InvalidVitalsError("Blood pressure needs both systolic and diastolic.")
    if systolic is not None and diastolic is not None and diastolic >= systolic:
        raise InvalidVitalsError("Diastolic must be lower than systolic.")


def _clean_moment(moment: datetime | None, now: datetime) -> datetime:
    if moment is None:
        return now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InvalidVitalsError("The time taken must include a time zone.")
    if moment > now + CLOCK_SKEW:
        raise InvalidVitalsError("Vitals cannot be taken in the future.")
    return moment.astimezone(UTC)


def _encounter(session: Session, *, tenant_id: uuid.UUID, encounter_id: uuid.UUID) -> Encounter:
    found = get_in_tenant(session, Encounter, tenant_id=tenant_id, row_id=encounter_id)
    if not isinstance(found, Encounter):
        raise EncounterNotFoundError("Encounter not found.")
    return found


def _existing(session: Session, *, tenant_id: uuid.UUID, vitals_id: uuid.UUID | None):
    if vitals_id is None:
        return None
    found = get_in_tenant(session, VitalSigns, tenant_id=tenant_id, row_id=vitals_id)
    return found if isinstance(found, VitalSigns) else None


def record_vitals(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    readings: VitalReadings,
    measured_at: datetime | None = None,
    vitals_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> VitalSigns:
    """Add a set of vitals to an open encounter. Any active clinician may add.

    vitals_id may come from the device; sending the same one again changes nothing.
    """
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, vitals_id=vitals_id)
    if existing is not None:
        return existing

    check_readings(readings)
    taken = _clean_moment(measured_at, current)
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    if encounter.status != EncounterStatus.OPEN.value:
        raise EncounterNotOpenError("New vitals can only be added to an open encounter.")

    vitals = VitalSigns(
        id=vitals_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        status=VersionStatus.CURRENT.value,
        measured_at=taken,
        recorded_by_id=actor_id,
        recorded_at=current,
        **asdict(readings),
    )
    session.add(vitals)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.VITALS_RECORD,
        patient_id=encounter.patient_id,
        entity_id=vitals.id,
    )
    session.commit()
    session.refresh(vitals)
    return vitals


def correct_vitals(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    vitals_id: uuid.UUID,
    readings: VitalReadings,
    correction_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> VitalSigns:
    """Replace a set with a corrected one. The old set is kept, unchanged, as superseded.

    Allowed after the encounter is closed too: changes after sign-off are new versions.
    """
    current = now or datetime.now(UTC)
    _require_clinician(session, tenant_id=tenant_id, actor_id=actor_id)
    existing = _existing(session, tenant_id=tenant_id, vitals_id=correction_id)
    if existing is not None:
        return existing

    check_readings(readings)
    statement = (
        tenant_select(VitalSigns, tenant_id)
        .where(col(VitalSigns.id) == vitals_id)
        .with_for_update()
    )
    old = session.exec(statement).first()
    if old is None:
        raise VitalsNotFoundError("Vitals not found.")
    if old.status != VersionStatus.CURRENT.value:
        raise NotCurrentVersionError("These vitals were already corrected; correct the newest.")

    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=old.encounter_id)
    if encounter.status == EncounterStatus.ENTERED_IN_ERROR.value:
        raise EncounterNotOpenError("This encounter was marked as entered in error.")
    if actor_id not in (old.recorded_by_id, encounter.clinician_id):
        raise NotVitalsAuthorError(
            "Only whoever recorded these vitals, or the encounter's owner, can correct them."
        )

    old.status = VersionStatus.SUPERSEDED.value
    corrected = VitalSigns(
        id=correction_id or uuid.uuid4(),
        tenant_id=tenant_id,
        encounter_id=old.encounter_id,
        patient_id=old.patient_id,
        status=VersionStatus.CURRENT.value,
        replaces_id=old.id,
        measured_at=old.measured_at,  # the same measurement, recorded correctly
        recorded_by_id=actor_id,
        recorded_at=current,
        **asdict(readings),
    )
    session.add(old)
    session.add(corrected)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.VITALS_CORRECT,
        patient_id=old.patient_id,
        entity_id=corrected.id,
    )
    session.commit()
    session.refresh(corrected)
    return corrected


def list_encounter_vitals(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    encounter_id: uuid.UUID,
    include_history: bool = False,
) -> list[VitalSigns]:
    """An encounter's vitals, oldest first. With history, superseded versions are included."""
    encounter = _encounter(session, tenant_id=tenant_id, encounter_id=encounter_id)
    add_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.VITALS_VIEW,
        patient_id=encounter.patient_id,
        entity_id=encounter.id,
    )
    session.commit()
    statement = tenant_select(VitalSigns, tenant_id).where(
        col(VitalSigns.encounter_id) == encounter_id
    )
    if not include_history:
        statement = statement.where(col(VitalSigns.status) == VersionStatus.CURRENT.value)
    statement = statement.order_by(col(VitalSigns.measured_at), col(VitalSigns.recorded_at))
    return list(session.exec(statement).all())
