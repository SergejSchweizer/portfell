import pytest

from portfell.selection_v2_contract import (
    SELECTION_V2_CONFIGURATIONS,
    SELECTION_V2_POLICY,
    SelectionV2ComparisonPolicy,
)


def test_selection_v2_has_exact_family_and_frozen_policy() -> None:
    assert len(SELECTION_V2_CONFIGURATIONS) == 14
    assert [
        sum(item.method == method for item in SELECTION_V2_CONFIGURATIONS)
        for method in (
            "equal_weight",
            "inverse_volatility",
            "minimum_variance",
            "equal_risk_contribution",
            "hierarchical_risk_parity",
            "minimum_cvar",
        )
    ] == [1, 3, 3, 3, 3, 1]
    assert SELECTION_V2_POLICY.to_row() == {
        "minimum_training_observations": 252,
        "test_window_observations": 21,
        "maximum_refit_count": 8,
        "minimum_completed_splits": 2,
    }


def test_selection_v2_policy_cannot_be_weakened() -> None:
    with pytest.raises(ValueError, match="frozen"):
        SelectionV2ComparisonPolicy(minimum_training_observations=100)
