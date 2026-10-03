"""Canonical Portfolio Selection v2 comparison contract.

This contract is deliberately independent of the legacy walk-forward default:
changing that default must not change the production comparison family.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_risk_spec import (
    EWMA_094,
    LW_FULL,
    LW_ROLLING_252,
    RiskModelSpecification,
)

SELECTION_V2_CONTRACT = ContractVersion("portfolio_selection_v2.comparison", 1)


@dataclass(frozen=True)
class SelectionV2ComparisonPolicy:
    minimum_training_observations: int = 252
    test_window_observations: int = 21
    maximum_refit_count: int = 8
    minimum_completed_splits: int = 2

    def __post_init__(self) -> None:
        if self.minimum_training_observations != 252 or self.test_window_observations != 21:
            raise ValueError("selection_v2_split_policy_is_frozen")
        if self.maximum_refit_count != 8 or self.minimum_completed_splits != 2:
            raise ValueError("selection_v2_split_policy_is_frozen")

    @property
    def fingerprint(self) -> str:
        return stable_contract_id("selection_v2_split_policy", self.to_row())

    def to_row(self) -> dict[str, int]:
        return {
            "minimum_training_observations": self.minimum_training_observations,
            "test_window_observations": self.test_window_observations,
            "maximum_refit_count": self.maximum_refit_count,
            "minimum_completed_splits": self.minimum_completed_splits,
        }


@dataclass(frozen=True)
class SelectionV2Configuration:
    method: str
    risk_model_spec: RiskModelSpecification

    @property
    def configuration_id(self) -> str:
        return stable_contract_id(
            "portfolio_selection_v2_configuration",
            {
                "contract": SELECTION_V2_CONTRACT.qualified_name,
                "method": self.method,
                "risk_model_spec_id": self.risk_model_spec.spec_id,
            },
        )

    def to_row(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "method": self.method,
            "spec_key": self.risk_model_spec.spec_key,
            "risk_model_spec_key": self.risk_model_spec.spec_key,
            "risk_model_spec_id": self.risk_model_spec.spec_id,
        }


SELECTION_V2_POLICY = SelectionV2ComparisonPolicy()
_FULL = (LW_FULL,)
_ALL = (LW_FULL, LW_ROLLING_252, EWMA_094)
SELECTION_V2_CONFIGURATIONS = tuple(
    SelectionV2Configuration(method, spec)
    for method, specs in (
        ("equal_weight", _FULL),
        ("inverse_volatility", _ALL),
        ("minimum_variance", _ALL),
        ("equal_risk_contribution", _ALL),
        ("hierarchical_risk_parity", _ALL),
        ("minimum_cvar", _FULL),
    )
    for spec in specs
)

if len({item.configuration_id for item in SELECTION_V2_CONFIGURATIONS}) != 14:
    raise RuntimeError("selection_v2_configuration_contract_collision")

__all__ = [
    "SELECTION_V2_CONFIGURATIONS",
    "SELECTION_V2_CONTRACT",
    "SELECTION_V2_POLICY",
    "SelectionV2ComparisonPolicy",
    "SelectionV2Configuration",
]
