"""Canonical risk-model artifact used by Multivariate portfolio candidates.

The adapter in this module is the only bridge from a scoped Multivariate input
snapshot to the numerical portfolio solvers.  It prevents a caller from
validating a joint shrinkage matrix and then silently reading pairwise sample
covariance rows for optimisation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_inputs import MultivariateInputSnapshot, MultivariateListingKey
from portfell.risk_model import RiskModelResult, estimate_risk_model
from portfell.table_io import JsonRow

RISK_MODEL_ARTIFACT_CONTRACT = ContractVersion("multivariate.risk_model", 2)
PRODUCTION_ESTIMATOR = "ledoit_wolf"


@dataclass(frozen=True)
class CanonicalCovarianceInput:
    """Pure solver input derived from exactly one validated artifact."""

    risk_model_id: str
    listings: tuple[MultivariateListingKey, ...]
    covariance: tuple[tuple[float, ...], ...]

    def covariance_rows(self) -> tuple[JsonRow, ...]:
        return tuple(
            {
                "left_isin": left.isin,
                "left_exchange": left.exchange,
                "left_code": left.code,
                "right_isin": right.isin,
                "right_exchange": right.exchange,
                "right_code": right.code,
                "covariance": self.covariance[left_index][right_index],
                "risk_model_id": self.risk_model_id,
            }
            for left_index, left in enumerate(self.listings)
            for right_index, right in enumerate(self.listings)
        )


@dataclass(frozen=True)
class MultivariateRiskModelArtifact:
    """Immutable joint covariance artifact plus its availability diagnostics."""

    risk_model_id: str
    input_snapshot_id: str
    contract_version: ContractVersion
    estimator: str
    return_type: str
    window_policy: str
    estimator_parameters: tuple[tuple[str, float], ...]
    listings: tuple[MultivariateListingKey, ...]
    aligned_calendar_id: str
    date_start: str
    date_end: str
    observation_count: int
    covariance: tuple[tuple[float, ...], ...]
    shrinkage_intensity: float | None
    minimum_eigenvalue: float | None
    condition_number: float | None
    is_positive_semidefinite: bool
    availability_reasons: tuple[str, ...]
    algorithm_version: int

    @property
    def available(self) -> bool:
        return not self.availability_reasons

    def solver_input(self) -> CanonicalCovarianceInput:
        if not self.available:
            raise ValueError("risk model is unavailable")
        return CanonicalCovarianceInput(self.risk_model_id, self.listings, self.covariance)


def build_multivariate_risk_model(
    *,
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    estimator: str = PRODUCTION_ESTIMATOR,
    window_policy: str = "full",
    estimator_parameters: Mapping[str, float] | None = None,
) -> MultivariateRiskModelArtifact:
    """Estimate the snapshot's one joint risk model and persistable identity."""

    if not snapshot.eligible:
        return _unavailable(snapshot, estimator, window_policy, "input_snapshot_unavailable")
    parameters = tuple(sorted((estimator_parameters or {}).items()))
    try:
        result = estimate_risk_model(
            return_rows,
            listings=tuple(key.as_tuple() for key in snapshot.listing_keys),
            estimator=estimator,
            window_policy=window_policy,
            ewma_decay=dict(parameters).get("ewma_decay", 0.94),
        )
    except (TypeError, ValueError) as error:
        return _unavailable(
            snapshot, estimator, window_policy, f"risk_model_error:{error}", parameters
        )
    reasons = tuple(sorted(result.diagnostics.availability_reasons))
    return _artifact(snapshot, result, estimator, window_policy, parameters, reasons)


def _artifact(
    snapshot: MultivariateInputSnapshot,
    result: RiskModelResult,
    estimator: str,
    window_policy: str,
    parameters: tuple[tuple[str, float], ...],
    reasons: tuple[str, ...],
) -> MultivariateRiskModelArtifact:
    listings = tuple(MultivariateListingKey(*item) for item in result.listings)
    identity = _risk_model_identity(
        snapshot=snapshot,
        listings=listings,
        estimator=estimator,
        window_policy=window_policy,
        parameters=parameters,
        covariance=result.covariance,
        algorithm_version=result.diagnostics.algorithm_version,
    )
    diagnostics = result.diagnostics
    return MultivariateRiskModelArtifact(
        risk_model_id=identity,
        input_snapshot_id=snapshot.snapshot_id,
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator=estimator,
        return_type=diagnostics.return_type,
        window_policy=window_policy,
        estimator_parameters=parameters,
        listings=listings,
        aligned_calendar_id=snapshot.aligned_calendar_id,
        date_start=diagnostics.first_date,
        date_end=diagnostics.last_date,
        observation_count=diagnostics.observation_count,
        covariance=result.covariance,
        shrinkage_intensity=diagnostics.shrinkage_intensity,
        minimum_eigenvalue=diagnostics.minimum_eigenvalue,
        condition_number=diagnostics.condition_number,
        is_positive_semidefinite=diagnostics.is_positive_semidefinite,
        availability_reasons=reasons,
        algorithm_version=diagnostics.algorithm_version,
    )


def _unavailable(
    snapshot: MultivariateInputSnapshot,
    estimator: str,
    window_policy: str,
    reason: str,
    parameters: tuple[tuple[str, float], ...] = (),
) -> MultivariateRiskModelArtifact:
    identity = _risk_model_identity(
        snapshot=snapshot,
        listings=snapshot.listing_keys,
        estimator=estimator,
        window_policy=window_policy,
        parameters=parameters,
        covariance=(),
        algorithm_version=1,
    )
    return MultivariateRiskModelArtifact(
        risk_model_id=identity,
        input_snapshot_id=snapshot.snapshot_id,
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator=estimator,
        return_type="log",
        window_policy=window_policy,
        estimator_parameters=parameters,
        listings=snapshot.listing_keys,
        aligned_calendar_id=snapshot.aligned_calendar_id,
        date_start=snapshot.date_start,
        date_end=snapshot.date_end,
        observation_count=snapshot.observation_count,
        covariance=(),
        shrinkage_intensity=None,
        minimum_eigenvalue=None,
        condition_number=None,
        is_positive_semidefinite=False,
        availability_reasons=(reason,),
        algorithm_version=1,
    )


def _risk_model_identity(
    *,
    snapshot: MultivariateInputSnapshot,
    listings: Sequence[MultivariateListingKey],
    estimator: str,
    window_policy: str,
    parameters: Sequence[tuple[str, float]],
    covariance: Sequence[Sequence[float]],
    algorithm_version: int,
) -> str:
    if any(not isfinite(value) for row in covariance for value in row):
        covariance_payload: object = "non_finite"
    else:
        covariance_payload = [list(row) for row in covariance]
    return stable_contract_id(
        "multivariate_risk_model",
        {
            "contract_version": RISK_MODEL_ARTIFACT_CONTRACT.qualified_name,
            "snapshot_id": snapshot.snapshot_id,
            "calendar_id": snapshot.aligned_calendar_id,
            "listing_keys": [key.as_tuple() for key in listings],
            "estimator": estimator,
            "window_policy": window_policy,
            "parameters": list(parameters),
            "covariance": covariance_payload,
            "algorithm_version": algorithm_version,
        },
    )


__all__ = [
    "CanonicalCovarianceInput",
    "MultivariateRiskModelArtifact",
    "PRODUCTION_ESTIMATOR",
    "RISK_MODEL_ARTIFACT_CONTRACT",
    "build_multivariate_risk_model",
]
