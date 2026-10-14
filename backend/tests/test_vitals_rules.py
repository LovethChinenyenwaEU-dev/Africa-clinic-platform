from decimal import Decimal

import pytest

from app.modules.records.models import VitalSigns
from app.modules.records.vitals import (
    RANGES,
    READING_NAMES,
    InvalidVitalsError,
    VitalReadings,
    check_readings,
)

ALLOWED_COLUMNS = {
    "id",
    "tenant_id",
    "encounter_id",
    "patient_id",
    "status",
    "replaces_id",
    "systolic_mmhg",
    "diastolic_mmhg",
    "pulse_bpm",
    "respiratory_rate",
    "spo2_pct",
    "temperature_c",
    "weight_kg",
    "height_cm",
    "measured_at",
    "recorded_by_id",
    "recorded_at",
}


def test_vitals_table_holds_numbers_ids_and_times_only():
    """No comment column: free text about a patient belongs in notes, with its own rules."""
    assert set(VitalSigns.__table__.columns.keys()) == ALLOWED_COLUMNS


@pytest.mark.parametrize(
    "readings",
    [
        VitalReadings(systolic_mmhg=120, diastolic_mmhg=80),
        VitalReadings(temperature_c=Decimal("39.8")),  # high fever: abnormal but real
        VitalReadings(spo2_pct=82),  # low but possible
        VitalReadings(weight_kg=Decimal("2.85")),  # a newborn
        VitalReadings(temperature_c=Decimal("37.50")),  # trailing zero is fine
        VitalReadings(
            systolic_mmhg=180,
            diastolic_mmhg=110,
            pulse_bpm=110,
            respiratory_rate=24,
            spo2_pct=94,
            temperature_c=Decimal("38.2"),
            weight_kg=Decimal("71.5"),
            height_cm=Decimal("168.0"),
        ),
    ],
)
def test_real_readings_are_accepted_even_when_abnormal(readings):
    check_readings(readings)


@pytest.mark.parametrize(
    "readings",
    [
        VitalReadings(),  # nothing entered
        VitalReadings(temperature_c=Decimal("370")),  # missing decimal point
        VitalReadings(spo2_pct=150),
        VitalReadings(pulse_bpm=0),
        VitalReadings(weight_kg=Decimal("-5")),
        VitalReadings(temperature_c=Decimal("37.25")),  # more precise than a thermometer
        VitalReadings(systolic_mmhg=120),  # half a blood pressure
        VitalReadings(diastolic_mmhg=80),
        VitalReadings(systolic_mmhg=80, diastolic_mmhg=120),  # swapped
    ],
)
def test_typing_mistakes_are_refused(readings):
    with pytest.raises(InvalidVitalsError):
        check_readings(readings)


def test_messages_name_the_reading_the_way_staff_say_it():
    with pytest.raises(InvalidVitalsError) as caught:
        check_readings(VitalReadings(temperature_c=Decimal("370")))

    assert str(caught.value) == "Temperature (°C) must be between 25 and 45."
    assert "temperature_c" not in str(caught.value)


def test_every_reading_has_a_staff_name():
    assert set(READING_NAMES) == set(RANGES)
