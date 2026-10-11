import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    """One diary line. IDs and codes only; the clinic ID stays inside."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID
    patient_id: uuid.UUID | None
    action: str
    purpose: str | None
    occurred_at: datetime