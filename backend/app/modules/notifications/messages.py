"""The words a patient receives.

SMS can be read by anyone holding the phone, so a reminder never says the
patient's name, the clinician, the reason for the visit or anything clinical.
"""
from datetime import datetime, timedelta, timezone

# Nigeria is on West Africa Time all year (no daylight saving), so a fixed offset is exact.
WAT = timezone(timedelta(hours=1), "WAT")


def reminder_text(starts_at: datetime, visit_type: str) -> str:
    local = starts_at.astimezone(WAT)
    when = f"{local:%a} {local.day} {local:%b} at {local:%H:%M}"
    if visit_type == "teleconsult":
        return f"Reminder: you have an online consultation on {when}."
    return f"Reminder: you have a clinic appointment on {when}."
