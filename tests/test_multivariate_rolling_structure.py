from datetime import date, timedelta

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_rolling_structure import (
    ROLLING_MAX_WINDOWS,
    ROLLING_OBSERVATIONS,
    ROLLING_STRIDE,
    build_rolling_structure_diagnostics,
)


A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")


def _rows(count: int) -> tuple[dict[str, object], ...]:
    start = date(2024, 1, 1)
    return tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": (start + timedelta(days=index)).isoformat(),
            "return": (index % 17 - 8) * (0.001 if listing == A else 0.0014),
        }
        for index in range(count)
        for listing in (A, B)
    )


def test_rolling_contract_constants_are_frozen() -> None:
    assert (ROLLING_OBSERVATIONS, ROLLING_STRIDE, ROLLING_MAX_WINDOWS) == (252, 21, 24)


def test_rolling_windows_include_latest_and_step_exactly_21_observations() -> None:
    result = build_rolling_structure_diagnostics(return_rows=_rows(294), listings=(A, B))
    assert result.available
    assert len(result.rows) == 3
    assert all(row.observation_count == 252 for row in result.rows)
    starts = [row.date_start for row in result.rows]
    assert starts == sorted(starts)
    assert result.rows[-1].date_end == _rows(294)[-1]["date"]


def test_rolling_structure_fails_closed_below_252() -> None:
    result = build_rolling_structure_diagnostics(return_rows=_rows(251), listings=(A, B))
    assert not result.available
    assert result.availability_reasons == ("rolling_structure_insufficient_history",)
