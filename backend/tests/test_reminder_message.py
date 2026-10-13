from datetime import UTC, datetime

from app.modules.notifications.messages import reminder_text

# Monday 2 November 2026, 09:00 UTC, which is 10:00 in Lagos.
START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def test_the_time_is_shown_in_nigerian_time():
    assert reminder_text(START, "in_person") == (
        "Reminder: you have a clinic appointment on Mon 2 Nov at 10:00."
    )


def test_an_online_visit_says_so():
    assert reminder_text(START, "teleconsult") == (
        "Reminder: you have an online consultation on Mon 2 Nov at 10:00."
    )
