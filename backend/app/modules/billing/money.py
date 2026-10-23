"""Money as people read it. Amounts are always whole kobo inside the system."""


def naira(kobo: int) -> str:
    """500000 -> "₦5,000.00"."""
    sign = "-" if kobo < 0 else ""
    whole, part = divmod(abs(kobo), 100)
    return f"{sign}₦{whole:,}.{part:02d}"
