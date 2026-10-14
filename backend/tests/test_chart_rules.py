from datetime import date, timedelta

import pytest

from app.modules.records.chart import (
    AllergyDetails,
    InvalidChartEntryError,
    ProblemDetails,
    clean_allergy,
    clean_problem,
)
from app.modules.records.models import Allergy, Problem

TODAY = date(2026, 11, 2)
SHARED = {
    "id",
    "tenant_id",
    "patient_id",
    "encounter_id",
    "version_status",
    "replaces_id",
    "clinical_status",
    "recorded_by_id",
    "recorded_at",
}


def test_allergy_table_columns_are_exactly_these():
    """A new column on a health table is a decision: this test makes it a visible one."""
    assert set(Allergy.__table__.columns.keys()) == SHARED | {"substance", "reaction", "severity"}


def test_problem_table_columns_are_exactly_these():
    assert set(Problem.__table__.columns.keys()) == SHARED | {
        "category",
        "description",
        "code",
        "onset_date",
    }


def test_allergy_text_is_tidied_and_defaults_are_safe():
    values = clean_allergy(AllergyDetails(substance="  Penicillin   G ", reaction=""))

    assert values == {
        "substance": "Penicillin G",
        "reaction": None,
        "severity": "unknown",
        "clinical_status": "active",
    }


@pytest.mark.parametrize(
    "details",
    [
        AllergyDetails(substance="   "),
        AllergyDetails(substance="x" * 201),
        AllergyDetails(substance="Penicillin", reaction="x" * 501),
        AllergyDetails(substance="Penicillin", severity="deadly"),
        AllergyDetails(substance="Penicillin", clinical_status="maybe"),
    ],
)
def test_bad_allergies_are_refused(details):
    with pytest.raises(InvalidChartEntryError):
        clean_allergy(details)


def test_problem_codes_are_tidied_to_capitals():
    values = clean_problem(
        ProblemDetails(description="Uncomplicated malaria", code=" b54 "), today=TODAY
    )

    assert values["code"] == "B54"
    assert values["category"] == "problem_list"
    assert values["clinical_status"] == "active"


@pytest.mark.parametrize("code", ["B54", "J45.9", "E11.65", "I10"])
def test_real_icd10_codes_are_accepted(code):
    clean_problem(ProblemDetails(description="Something", code=code), today=TODAY)


@pytest.mark.parametrize(
    "details",
    [
        ProblemDetails(description=" "),
        ProblemDetails(description="x" * 501),
        ProblemDetails(description="Malaria", code="malaria"),
        ProblemDetails(description="Malaria", code="B5"),
        ProblemDetails(description="Malaria", category="rumour"),
        ProblemDetails(description="Malaria", clinical_status="cured"),
        ProblemDetails(description="Malaria", onset_date=TODAY + timedelta(days=1)),
    ],
)
def test_bad_problems_are_refused(details):
    with pytest.raises(InvalidChartEntryError):
        clean_problem(details, today=TODAY)
