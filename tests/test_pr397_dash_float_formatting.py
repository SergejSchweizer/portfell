import math

from portfell.dash_app.formatting import format_float


def test_float_formatting_is_fixed_and_normalizes_negative_zero() -> None:
    assert format_float(1.234567) == "1.23457"
    assert format_float(-1.234567) == "-1.23457"
    assert format_float(1.2) == "1.20000"
    assert format_float(0.000006) == "0.00001"
    assert format_float(-0.000001) == "0.00000"


def test_percent_and_unavailable_values_keep_presentation_semantics() -> None:
    assert format_float(0.125, percent=True) == "12.50000%"
    assert format_float(None) == "—"
    assert format_float(math.nan) == "—"
    assert format_float(math.inf, unavailable="N/A") == "N/A"
    assert format_float(3) == "3.00000"
