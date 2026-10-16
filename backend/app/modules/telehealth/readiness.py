"""Is a remote visit safe to run? Asked by scheduling before a teleconsult checks in or starts.

Kept apart from intake.py (which calls scheduling to check the patient in), so
scheduling can ask this without the two modules importing each other in a loop.
"""
import uuid
from enum import StrEnum

from sqlmodel import Session, col

from app.core.tenant_scope import tenant_select
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.statuses import VisitType
from app.modules.scheduling.transitions import InvalidMoveError
from app.modules.telehealth.models import TeleconsultIntake


class IntakeOutcome(StrEnum):
    READY = "ready"  # no danger signs: the patient may be seen remotely
    ESCALATED = "escalated"  # a danger sign: advised in-person care; no remote visit


def latest_intake(
    session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID
) -> TeleconsultIntake | None:
    """The intake that counts: the newest one."""
    statement = (
        tenant_select(TeleconsultIntake, tenant_id)
        .where(col(TeleconsultIntake.appointment_id) == appointment_id)
        .order_by(col(TeleconsultIntake.recorded_at).desc(), col(TeleconsultIntake.id))
    )
    return session.exec(statement).first()


def teleconsult_ready(session: Session, *, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> bool:
    """Yes only if the newest intake found no danger signs."""
    latest = latest_intake(session, tenant_id=tenant_id, appointment_id=appointment_id)
    return latest is not None and latest.outcome == IntakeOutcome.READY.value


def require_safe_teleconsult(session: Session, appointment: Appointment) -> None:
    """A remote visit checks in and starts only after an intake with no danger signs
    (FR-C2, FR-C6). Nobody can skip the screen by pressing "check in" or "start".
    In-person visits pass straight through."""
    if appointment.visit_type != VisitType.TELECONSULT.value:
        return
    ready = teleconsult_ready(
        session, tenant_id=appointment.tenant_id, appointment_id=appointment.id
    )
    if not ready:
        raise InvalidMoveError(
            "A remote visit needs its intake first, with no danger signs. "
            "With a danger sign the patient must be seen in person."
        )
