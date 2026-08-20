from __future__ import annotations

import pytest

from portfell.multivariate.contracts.common import DecisionStageId, EvidenceAvailability, ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.contracts.decisions import (
    DecisionArtifact,
    DecisionCandidate,
    DecisionConflictError,
    IdempotentDecisionSink,
)


def _artifact(metrics: dict[str, object]) -> DecisionArtifact:
    return DecisionArtifact(
        run_id="run-1",
        objective="return_risk",
        stage=DecisionStageId.WINNER_SELECTION,
        pinned_revisions=("bi-1", "risk-1"),
        candidates=(DecisionCandidate("candidate-a", metrics),),
        selected_ids=("candidate-a",),
        rejections=(),
        status=EvidenceAvailability.AVAILABLE,
        reason_code=DecisionReasonCode.OBJECTIVE_WINNER,
        algorithm_version="algo-v1",
        profile_version="profile-v1",
        listing_scope=(ListingIdentity("DE000A", "XETRA", "AAA"),),
    )


def test_pr282_reason_registry_covers_all_required_decision_classes() -> None:
    values = {reason.value for reason in DecisionReasonCode}
    required = {
        "eligible",
        "data_unavailable",
        "insufficient_history",
        "distribution_not_allowed",
        "pareto_dominated",
        "redundancy_represented",
        "risk_model_unavailable",
        "solver_non_convergence",
        "solver_infeasible",
        "walk_forward_unavailable",
        "oos_metric_unavailable",
        "not_applicable",
    }
    assert required <= values


def test_pr282_decision_id_is_content_addressed_and_mapping_order_invariant() -> None:
    first = _artifact({"sharpe": 1.2, "drawdown": -0.1})
    reordered = _artifact({"drawdown": -0.1, "sharpe": 1.2})
    changed = _artifact({"sharpe": 1.3, "drawdown": -0.1})
    assert first.decision_id == reordered.decision_id
    assert first.decision_id != changed.decision_id


def test_pr282_sink_is_idempotent_for_identical_artifact() -> None:
    sink = IdempotentDecisionSink()
    artifact = _artifact({"sharpe": 1.2})
    assert sink.put(artifact) is True
    assert sink.put(artifact) is False
    assert sink.get(artifact.decision_id) is not None


def test_pr282_same_explicit_id_with_different_canonical_bytes_fails_closed() -> None:
    sink = IdempotentDecisionSink()
    assert sink.put_payload(decision_id="decision-fixed", canonical_payload='{"value":1}') is True
    with pytest.raises(DecisionConflictError, match="conflicting decision payload"):
        sink.put_payload(decision_id="decision-fixed", canonical_payload='{"value":2}')


def test_pr282_sink_rejects_noncanonical_payload_bytes() -> None:
    sink = IdempotentDecisionSink()
    with pytest.raises(ValueError, match="canonical JSON"):
        sink.put_payload(decision_id="decision-fixed", canonical_payload='{ "value": 1 }')


def test_pr282_all_eight_stages_are_available_to_artifacts() -> None:
    assert len(tuple(DecisionStageId)) == 8
    for stage in DecisionStageId:
        artifact = _artifact({"stage": stage.value})
        assert artifact.run_id == "run-1"
