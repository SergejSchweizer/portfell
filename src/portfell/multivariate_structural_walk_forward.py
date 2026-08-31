"""Leakage-safe structural evidence for production walk-forward splits.

This module is additive evidence only. It reuses the production walk-forward
calendar and already-refitted candidates, fits structure on training rows only,
and copies the existing out-of-sample metrics from ``ValidationSplit`` without
re-ranking candidates or changing winner selection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_candidate_cluster_risk import build_candidate_cluster_risk
from portfell.multivariate_candidate_structure import build_candidate_pca_risk
from portfell.multivariate_candidate_structure_summary import summarize_candidate_pca_risk
from portfell.multivariate_candidates import CANDIDATE_CONTRACT, PortfolioCandidate
from portfell.multivariate_inputs import MultivariateInputSnapshot
from portfell.multivariate_risk_clusters import (
    RiskClusterDiagnostics,
    build_hierarchical_risk_clusters,
)
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    build_multivariate_risk_model,
)
from portfell.multivariate_structure_artifacts import (
    CANDIDATE_STRUCTURE_V2_CONTRACT,
    STRUCTURE_V3_CONTRACT,
)
from portfell.multivariate_structure_v2 import build_structure_pca_diagnostics
from portfell.multivariate_validation import (
    DEFAULT_WALK_FORWARD_POLICY,
    ValidationSplit,
    WalkForwardPolicy,
    walk_forward_training_rows,
)
from portfell.table_io import JsonRow

STRUCTURAL_WALK_FORWARD_CONTRACT = ContractVersion("multivariate.structural_walk_forward", 1)


@dataclass(frozen=True)
class StructuralWalkForwardEvidence:
    """Immutable training-structure + existing OOS evidence for one split/candidate."""

    evidence_id: str
    split_id: str
    candidate_id: str
    method: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    effective_pca_risk_drivers: float | None
    largest_pca_risk_share: float | None
    largest_cluster_gross_abs_risk_share: float | None
    post_cost_return: float
    volatility: float | None
    conditional_value_at_risk: float | None
    max_drawdown: float | None
    training_risk_model_id: str
    validation_contract_version: str
    candidate_contract_version: str
    risk_model_contract_version: str
    structure_contract_version: str
    candidate_structure_contract_version: str
    risk_model_algorithm_version: int
    availability_reasons: tuple[str, ...]

    def to_row(self) -> JsonRow:
        return {
            "contract_version": STRUCTURAL_WALK_FORWARD_CONTRACT.qualified_name,
            "evidence_id": self.evidence_id,
            "split_id": self.split_id,
            "candidate_id": self.candidate_id,
            "method": self.method,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "effective_pca_risk_drivers": self.effective_pca_risk_drivers,
            "largest_pca_risk_share": self.largest_pca_risk_share,
            "largest_cluster_gross_abs_risk_share": self.largest_cluster_gross_abs_risk_share,
            "post_cost_return": self.post_cost_return,
            "volatility": self.volatility,
            "conditional_value_at_risk": self.conditional_value_at_risk,
            "max_drawdown": self.max_drawdown,
            "training_risk_model_id": self.training_risk_model_id,
            "validation_contract_version": self.validation_contract_version,
            "candidate_contract_version": self.candidate_contract_version,
            "risk_model_contract_version": self.risk_model_contract_version,
            "structure_contract_version": self.structure_contract_version,
            "candidate_structure_contract_version": self.candidate_structure_contract_version,
            "risk_model_algorithm_version": self.risk_model_algorithm_version,
            "availability_reasons": list(self.availability_reasons),
        }


def build_structural_walk_forward_evidence(
    *,
    snapshot: MultivariateInputSnapshot,
    candidates: Sequence[PortfolioCandidate],
    return_rows: Sequence[Mapping[str, Any]],
    refitted_candidate_sets: Sequence[Sequence[PortfolioCandidate]],
    validation_splits: Sequence[ValidationSplit],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
) -> tuple[StructuralWalkForwardEvidence, ...]:
    """Build structure for each completed production split using train rows only.

    ``refitted_candidate_sets`` must be the same sequence passed to
    ``validate_candidates(..., precomputed_candidates=...)``. That makes this
    evidence share the exact production split calendar and candidate refit
    contract without solving a second set of portfolio weights.
    """

    training_windows = walk_forward_training_rows(
        candidates=candidates,
        return_rows=return_rows,
        policy=policy,
    )
    if len(training_windows) != len(refitted_candidate_sets):
        raise ValueError("structural_walk_forward_refit_count_mismatch")

    completed = tuple(split for split in validation_splits if split.status == "complete")
    evidence: list[StructuralWalkForwardEvidence] = []
    consumed_split_ids: set[str] = set()

    for training_rows, refitted in zip(training_windows, refitted_candidate_sets, strict=True):
        train_dates = tuple(
            sorted({str(row.get("date", "")) for row in training_rows if row.get("date")})
        )
        if not train_dates:
            raise ValueError("structural_walk_forward_training_rows_missing")
        train_start = train_dates[0]
        train_end = train_dates[-1]
        window_splits = tuple(split for split in completed if split.train_end == train_end)
        if not window_splits:
            raise ValueError("structural_walk_forward_split_missing")

        earliest_test_start = min(split.test_start for split in window_splits)
        if train_end >= earliest_test_start:
            raise ValueError("structural_walk_forward_future_leakage")
        if any(str(row.get("date", "")) >= earliest_test_start for row in training_rows):
            raise ValueError("structural_walk_forward_future_leakage")

        risk_model = build_multivariate_risk_model(
            snapshot=snapshot,
            return_rows=training_rows,
            estimator="ledoit_wolf",
            window_policy="full",
        )
        pca = build_structure_pca_diagnostics(risk_model)
        clusters = (
            build_hierarchical_risk_clusters(
                listings=risk_model.listings,
                correlation=pca.correlation_matrix,
            )
            if pca.correlation.available and pca.correlation_matrix
            else RiskClusterDiagnostics((), None, None, ("clusters_unavailable",))
        )
        refitted_by_identity = {
            (candidate.candidate_id, candidate.method): candidate for candidate in refitted
        }

        for split in window_splits:
            if split.train_start != train_start or split.train_end >= split.test_start:
                raise ValueError("structural_walk_forward_calendar_mismatch")
            candidate = refitted_by_identity.get((split.candidate_id, split.method))
            if candidate is None:
                raise ValueError("structural_walk_forward_refitted_candidate_missing")
            pca_risk = build_candidate_pca_risk(candidate=candidate, risk_model=risk_model)
            summary = summarize_candidate_pca_risk(pca_risk)
            cluster_risk = build_candidate_cluster_risk(
                candidate=candidate,
                risk_model=risk_model,
                clusters=clusters,
            )
            largest_cluster_share = (
                max((row.gross_abs_risk_share for row in cluster_risk.rows), default=None)
                if cluster_risk.available
                else None
            )
            reasons = tuple(
                sorted(
                    set(
                        (
                            *risk_model.availability_reasons,
                            *pca.covariance.availability_reasons,
                            *pca.correlation.availability_reasons,
                            *clusters.availability_reasons,
                            *pca_risk.availability_reasons,
                            *summary.availability_reasons,
                            *cluster_risk.availability_reasons,
                        )
                    )
                )
            )
            identity_payload = {
                "contract": STRUCTURAL_WALK_FORWARD_CONTRACT.qualified_name,
                "split_id": split.split_id,
                "candidate_id": split.candidate_id,
                "method": split.method,
                "train_start": split.train_start,
                "train_end": split.train_end,
                "test_start": split.test_start,
                "test_end": split.test_end,
                "training_risk_model_id": risk_model.risk_model_id,
                "validation_contract": policy.version.qualified_name,
                "candidate_contract": CANDIDATE_CONTRACT.qualified_name,
                "risk_model_contract": RISK_MODEL_ARTIFACT_CONTRACT.qualified_name,
                "structure_contract": STRUCTURE_V3_CONTRACT.qualified_name,
                "candidate_structure_contract": CANDIDATE_STRUCTURE_V2_CONTRACT.qualified_name,
                "risk_model_algorithm_version": risk_model.algorithm_version,
                "effective_pca_risk_drivers": summary.effective_pca_risk_drivers,
                "largest_pca_risk_share": summary.largest_pca_risk_share,
                "largest_cluster_gross_abs_risk_share": largest_cluster_share,
                "post_cost_return": split.post_cost_return,
                "volatility": split.volatility,
                "conditional_value_at_risk": split.conditional_value_at_risk,
                "max_drawdown": split.max_drawdown,
                "availability_reasons": list(reasons),
            }
            evidence.append(
                StructuralWalkForwardEvidence(
                    evidence_id=stable_contract_id(
                        "structural_walk_forward_evidence",
                        identity_payload,
                    ),
                    split_id=split.split_id,
                    candidate_id=split.candidate_id,
                    method=split.method,
                    train_start=split.train_start,
                    train_end=split.train_end,
                    test_start=split.test_start,
                    test_end=split.test_end,
                    effective_pca_risk_drivers=summary.effective_pca_risk_drivers,
                    largest_pca_risk_share=summary.largest_pca_risk_share,
                    largest_cluster_gross_abs_risk_share=largest_cluster_share,
                    post_cost_return=split.post_cost_return,
                    volatility=split.volatility,
                    conditional_value_at_risk=split.conditional_value_at_risk,
                    max_drawdown=split.max_drawdown,
                    training_risk_model_id=risk_model.risk_model_id,
                    validation_contract_version=policy.version.qualified_name,
                    candidate_contract_version=CANDIDATE_CONTRACT.qualified_name,
                    risk_model_contract_version=RISK_MODEL_ARTIFACT_CONTRACT.qualified_name,
                    structure_contract_version=STRUCTURE_V3_CONTRACT.qualified_name,
                    candidate_structure_contract_version=CANDIDATE_STRUCTURE_V2_CONTRACT.qualified_name,
                    risk_model_algorithm_version=risk_model.algorithm_version,
                    availability_reasons=reasons,
                )
            )
            consumed_split_ids.add(split.split_id)

    expected_split_ids = {split.split_id for split in completed}
    if consumed_split_ids != expected_split_ids:
        raise ValueError("structural_walk_forward_unmatched_completed_split")
    return tuple(
        sorted(
            evidence,
            key=lambda row: (row.test_start, row.method, row.candidate_id, row.split_id),
        )
    )


def structural_walk_forward_rows(
    values: Sequence[StructuralWalkForwardEvidence],
) -> tuple[JsonRow, ...]:
    """Return deterministic JSON-safe rows for generic artifact persistence."""

    return tuple(value.to_row() for value in values)


__all__ = [
    "STRUCTURAL_WALK_FORWARD_CONTRACT",
    "StructuralWalkForwardEvidence",
    "build_structural_walk_forward_evidence",
    "structural_walk_forward_rows",
]
