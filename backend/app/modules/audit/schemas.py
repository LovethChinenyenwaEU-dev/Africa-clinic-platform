import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    """One diary line. IDs and codes only; the clinic ID stays inside."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID
    patient_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    device_id: uuid.UUID | None
    action: str
    purpose: str | None
    occurred_at: datetime

class ChainCheckResponse(BaseModel):
    """The tamper-evident check. Write head_seq and head_hash down to anchor the chain."""

    model_config = ConfigDict(from_attributes=True)

    ok: bool
    lines_checked: int
    broken_at: int | None
    problem: str | None
    head_seq: int
    head_hash: str
