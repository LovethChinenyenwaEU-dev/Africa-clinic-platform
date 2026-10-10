import re


class InvalidPhoneError(ValueError):
    """The phone number cannot be understood."""


_SEPARATORS = re.compile(r"[\s\-().]")


def normalise_phone(raw: str) -> str:
    """Turn a typed phone number into one standard form, like +2348031234567.

    Nigerian numbers may be typed with 0, 234 or +234 in front. Other countries
    are accepted only when typed with a + (or 00) and a country code.
    """
    text = _SEPARATORS.sub("", raw)
    if not text:
        raise InvalidPhoneError("Phone number cannot be empty.")

    if text.startswith("00"):
        text = "+" + text[2:]
    has_plus = text.startswith("+")
    digits = text[1:] if has_plus else text
    if not digits.isdigit():
        raise InvalidPhoneError("Phone number can only contain digits, spaces and + - ( ).")

    if has_plus or digits.startswith("234"):
        national = digits
    elif digits.startswith("0"):
        national = "234" + digits[1:]
    else:
        national = "234" + digits

    if national.startswith("234"):
        if len(national) != 13 or national[3] == "0":
            raise InvalidPhoneError("That does not look like a valid Nigerian phone number.")
    elif len(national) < 8 or len(national) > 15 or national[0] == "0":
        raise InvalidPhoneError("That does not look like a valid international phone number.")

    return "+" + national