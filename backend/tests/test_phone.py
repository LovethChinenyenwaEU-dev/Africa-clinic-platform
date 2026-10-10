import pytest

from app.modules.patients.phone import InvalidPhoneError, normalise_phone


@pytest.mark.parametrize(
    "typed",
    [
        "08031234567",
        "0803 123 4567",
        "(0803) 123-4567",
        "8031234567",
        "2348031234567",
        "+2348031234567",
        "+234 803 123 4567",
        "002348031234567",
        "  08031234567  ",
    ],
)
def test_nigerian_numbers_all_become_the_same_standard_form(typed):
    assert normalise_phone(typed) == "+2348031234567"


def test_foreign_numbers_need_a_plus_and_keep_their_country_code():
    assert normalise_phone("+1 415 555 2671") == "+14155552671"
    assert normalise_phone("0044 20 7946 0958") == "+442079460958"


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "   ",
        "abc",
        "0803",
        "080312345678",
        "08031234567x",
        "+2340803123456",
        "+0123456789",
        "+123",
    ],
)
def test_bad_numbers_are_refused(typed):
    with pytest.raises(InvalidPhoneError):
        normalise_phone(typed)