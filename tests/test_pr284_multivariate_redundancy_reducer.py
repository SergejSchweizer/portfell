from __future__ import annotations

import inspect

from portfell.multivariate.contracts.common import DecisionStageId, EvidenceAvailability, ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.selector.redundancy import (
    RedundancyCandidate,
    reduce_redundancy,
    redundancy_evidence,
)


def _candidate(index: int) -> RedundancyCandidate:
    listing = ListingIdentity(f"ISIN-{index:04d}", "XETRA", f"C{index:04d}")
    return RedundancyCandidate(
        listing=listing,
        pareto_rank=1 + index % 3,
        sortino=2.0 - index / 10000,
        annualized_geometric_return=0.10 - index / 100000,
        expected_shortfall=0.02 + index / 100000,
        annualized_volatility=0.10 + index / 100000,
    )


def _pair_values(
    candidates: tuple[RedundancyCandidate, ...], value: float
) -> dict[tuple[ListingIdentity, ListingIdentity], float]:
    listings = tuple(candidate.listing for candidate in candidates)
    return {
        (listings[left], listings[right]): value
        for left in range(len(listings))
        for right in range(left + 1, len(listings))
    }


def test_pr284_at_or_below_250_is_typed_not_applicable_and_unchanged() -> None:
    candidates = tuple(_candidate(index) for index in range(250))
    result = reduce_redundancy(candidates, correlations={})
    assert result.applied is False
    assert result.availability is EvidenceAvailability.NOT_APPLICABLE
    assert result.reason_code is DecisionReasonCode.REDUNDANCY_NOT_REQUIRED
    assert result.selected == tuple(candidate.listing for candidate in candidates)
    assert result.rejected == ()


def test_pr284_400_listing_fixture_reduces_to_exactly_250_unique_subset() -> None:
    candidates = tuple(_candidate(index) for index in range(400))
    correlations = _pair_values(candidates, 0.5)
    result = reduce_redundancy(candidates, correlations=correlations)
    assert result.applied is True
    assert result.availability is EvidenceAvailability.AVAILABLE
    assert len(result.selected) == 250
    assert len(set(result.selected)) == 250
    assert set(result.selected) <= {candidate.listing for candidate in candidates}
    assert len(result.rejected) == 150


def test_pr284_reversed_input_and_worker_independence_are_deterministic() -> None:
    candidates = tuple(_candidate(index) for index in range(260))
    correlations = _pair_values(candidates, 0.4)
    forward = reduce_redundancy(candidates, correlations=correlations)
    reverse = reduce_redundancy(tuple(reversed(candidates)), correlations=correlations)
    assert forward == reverse
    assert "worker" not in inspect.signature(reduce_redundancy).parameters


def test_pr284_rejection_records_dependence_tail_drawdown_and_history_impact() -> None:
    candidates = tuple(_candidate(index) for index in range(251))
    correlations = _pair_values(candidates, 0.8)
    tail = _pair_values(candidates, 0.3)
    drawdown = _pair_values(candidates, 0.2)
    result = reduce_redundancy(
        candidates,
        correlations=correlations,
        tail_dependence=tail,
        drawdown_overlap=drawdown,
        before_common_observations=1500,
        after_common_observations=1600,
    )
    assert len(result.selected) == 250
    assert len(result.rejected) == 1
    rejection = result.rejected[0]
    assert rejection.pearson == 0.8
    assert rejection.tail_dependence == 0.3
    assert rejection.drawdown_overlap == 0.2
    assert rejection.before_common_observations == 1500
    assert rejection.after_common_observations == 1600


def test_pr284_stage_evidence_contains_decision_and_before_after_snapshots() -> None:
    candidates = tuple(_candidate(index) for index in range(251))
    result = reduce_redundancy(candidates, correlations=_pair_values(candidates, 0.8))
    evidence = redundancy_evidence(
        run_id="run-1",
        objective="return_risk",
        project_slug="alpha",
        pinned_revision="bi-1",
        candidates=candidates,
        result=result,
        algorithm_version="algo-v1",
        profile_version="profile-v1",
    )
    assert evidence.decision.stage is DecisionStageId.BIVARIATE_REDUNDANCY
    assert evidence.before_snapshot.listing_count == 251
    assert evidence.after_snapshot.listing_count == 250
    assert evidence.after_snapshot.removed_count == 1
