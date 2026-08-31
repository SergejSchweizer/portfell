import pytest

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_signal_components import (
    PARALLEL_QUANTILE,
    PARALLEL_QUANTILE_METHOD,
    PARALLEL_REPLICATES,
    PARALLEL_SEED,
    build_signal_component_diagnostics,
)


def test_parallel_analysis_contract_is_frozen() -> None:
    assert PARALLEL_REPLICATES == 100
    assert PARALLEL_SEED == 41
    assert PARALLEL_QUANTILE == 0.95
    assert PARALLEL_QUANTILE_METHOD == "higher"


def test_parallel_analysis_is_deterministic_when_numpy_is_available() -> None:
    pytest.importorskip("numpy")
    listings = (MultivariateListingKey("IE1", "X", "A"), MultivariateListingKey("IE2", "X", "B"))
    rows = tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": f"2025-01-{day:02d}",
            "return": (day - 6) * (0.001 if index == 0 else 0.0015),
        }
        for day in range(1, 12)
        for index, listing in enumerate(listings)
    )
    first = build_signal_component_diagnostics(return_rows=rows, listings=listings)
    second = build_signal_component_diagnostics(return_rows=rows, listings=listings)
    assert first == second
    assert first.replicate_count == 100
    assert first.seed == 41
