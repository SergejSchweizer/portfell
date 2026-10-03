"""Immutable, versioned specifications for production risk-model fits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from portfell.contract_versioning import ContractVersion, stable_contract_id

RISK_MODEL_SPEC_CONTRACT = ContractVersion("multivariate.risk_model_spec", 1)


@dataclass(frozen=True)
class RiskModelSpecification:
    spec_key: str
    estimator: str
    window_policy: str
    return_type: str = "log"
    window_size: int | None = None
    ewma_decay: float | None = None
    contract: ClassVar[ContractVersion] = RISK_MODEL_SPEC_CONTRACT

    def __post_init__(self) -> None:
        if self.spec_key not in {"LW_FULL", "LW_ROLLING_252", "EWMA_094"}:
            raise ValueError("unknown_risk_model_spec")
        if self.return_type != "log":
            raise ValueError("production_risk_specs_require_log_returns")
        if self.spec_key == "LW_FULL" and (
            self.estimator,
            self.window_policy,
            self.window_size,
        ) != ("ledoit_wolf", "full", None):
            raise ValueError("LW_FULL_definition_mismatch")
        if self.spec_key == "LW_ROLLING_252" and (
            self.estimator,
            self.window_policy,
            self.window_size,
        ) != ("ledoit_wolf", "rolling", 252):
            raise ValueError("LW_ROLLING_252_definition_mismatch")
        if self.spec_key == "EWMA_094" and (
            self.estimator,
            self.window_policy,
            self.window_size,
        ) != ("ewma", "full", None):
            raise ValueError("EWMA_094_definition_mismatch")
        if self.spec_key == "EWMA_094" and self.ewma_decay != 0.94:
            raise ValueError("EWMA_094_definition_mismatch")
        if self.spec_key != "EWMA_094" and self.ewma_decay is not None:
            raise ValueError("irrelevant_ewma_parameter")

    @property
    def spec_id(self) -> str:
        return stable_contract_id(
            self.contract.name,
            {
                "contract": self.contract.qualified_name,
                "spec_key": self.spec_key,
                "estimator": self.estimator,
                "window_policy": self.window_policy,
                "return_type": self.return_type,
                "window_size": self.window_size,
                "ewma_decay": self.ewma_decay,
            },
        )


LW_FULL = RiskModelSpecification("LW_FULL", "ledoit_wolf", "full")
LW_ROLLING_252 = RiskModelSpecification("LW_ROLLING_252", "ledoit_wolf", "rolling", window_size=252)
EWMA_094 = RiskModelSpecification("EWMA_094", "ewma", "full", ewma_decay=0.94)
PRODUCTION_RISK_MODEL_SPECS = (LW_FULL, LW_ROLLING_252, EWMA_094)

__all__ = [
    "EWMA_094",
    "LW_FULL",
    "LW_ROLLING_252",
    "PRODUCTION_RISK_MODEL_SPECS",
    "RISK_MODEL_SPEC_CONTRACT",
    "RiskModelSpecification",
]
