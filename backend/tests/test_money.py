from app.modules.billing.money import naira


def test_kobo_is_shown_as_naira():
    assert naira(500_000) == "₦5,000.00"
    assert naira(123_456_789) == "₦1,234,567.89"
    assert naira(5) == "₦0.05"
    assert naira(0) == "₦0.00"
    assert naira(-150) == "-₦1.50"
