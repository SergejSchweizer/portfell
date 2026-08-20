"""Candidate configuration identities and split-local expected-return estimates."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum

from portfell.multivariate.candidates.risk_models import AlignedReturns, RiskModel
from portfell.multivariate.contracts.serialization import canonical_json


class CandidateMethodId(StrEnum):
    EQUAL_WEIGHT = "equal_weight"
    MINIMUM_VARIANCE = "minimum_variance"
    MAXIMUM_SHARPE = "maximum_sharpe"
    MAXIMUM_DIVERSIFICATION = "maximum_diversification"
    EQUAL_RISK_CONTRIBUTION = "equal_risk_contribution"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    MINIMUM_CVAR = "minimum_cvar"


@dataclass(frozen=True, slots=True)
class CandidateConfiguration:
    risk_model: RiskModel
    method: CandidateMethodId
    settings_version: str
    algorithm_version: str

    @property
    def configuration_id(self) -> str:
        return hashlib.sha256(canonical_json(self).encode()).hexdigest()


def annualized_expected_log_returns(aligned: AlignedReturns, *, trading_days: int = 252) -> tuple[float, ...]:
    """Estimate expected returns from the current training window only."""

    if not aligned.rows:
        raise ValueError("expected-return estimation requires observations")
    width = len(aligned.listings)
    result = []
    for index in range(width):
        mean_log_return = sum(row[index] for row in aligned.rows) / len(aligned.rows)
        annualized = math.expm1(mean_log_return * trading_days)
        result.append(annualized)
    return tuple(result)
