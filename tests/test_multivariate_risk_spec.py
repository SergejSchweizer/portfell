import pytest

from portfell.multivariate_risk_spec import (
    EWMA_094,
    LW_FULL,
    LW_ROLLING_252,
    RiskModelSpecification,
)
from portfell.risk_model import estimate_risk_model


def test_production_specs_are_readable_and_have_stable_ids() -> None:
    assert [spec.spec_key for spec in (LW_FULL, LW_ROLLING_252, EWMA_094)] == [
        "LW_FULL",
        "LW_ROLLING_252",
        "EWMA_094",
    ]
    assert LW_FULL.spec_id == RiskModelSpecification("LW_FULL", "ledoit_wolf", "full").spec_id
    assert LW_FULL.spec_id != LW_ROLLING_252.spec_id


def test_specs_reject_irrelevant_parameters() -> None:
    with pytest.raises(ValueError, match="LW_FULL_definition_mismatch"):
        RiskModelSpecification("LW_FULL", "ledoit_wolf", "full", window_size=252)


def test_rolling_window_requires_exact_observation_count() -> None:
    rows = [
        {"isin": "A", "exchange": "X", "code": "A", "date": f"2020-01-{day:02d}", "return": 0.01}
        for day in range(1, 6)
    ]
    with pytest.raises(ValueError, match="exact rolling window"):
        estimate_risk_model(
            rows,
            listings=[("A", "X", "A")],
            estimator="ledoit_wolf",
            window_policy="rolling",
            window_size=252,
        )
