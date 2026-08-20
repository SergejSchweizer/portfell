from __future__ import annotations

from portfell.multivariate.contracts.common import DecisionStageId, ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.selector.eligibility import (
    SelectorMetrics,
    apply_eligibility,
    eligibility_evidence,
)
from portfell.multivariate.selector.pareto import pareto_evidence, select_pareto


def _row(
    name: str,
    *,
    annual_return: float | None,
    sharpe: float | None,
    sortino: float | None,
    volatility: float | None,
    expected_shortfall: float | None,
    drawdown: float | None,
    observations: int | None = 252,
    frequency: str | None = "quarterly",
) -> SelectorMetrics:
    return SelectorMetrics(
        ListingIdentity(name, "XETRA", name),
        annual_return,
        sharpe,
        sortino,
        volatility,
        expected_shortfall,
        drawdown,
        observations,
        frequency,
    )


def test_pr270_eligibility_removes_only_with_explicit_reasons_and_is_order_invariant() -> None:
    rows = (
        _row("GOOD", annual_return=0.08, sharpe=1.0, sortino=1.2, volatility=0.1, expected_shortfall=0.03, drawdown=-0.1),
        _row("MISSING", annual_return=None, sharpe=1.0, sortino=1.2, volatility=0.1, expected_shortfall=0.03, drawdown=-0.1),
        _row("SHORT", annual_return=0.08, sharpe=1.0, sortino=1.2, volatility=0.1, expected_shortfall=0.03, drawdown=-0.1, observations=1),
        _row("FREQ", annual_return=0.08, sharpe=1.0, sortino=1.2, volatility=0.1, expected_shortfall=0.03, drawdown=-0.1, frequency="monthly"),
    )
    forward = apply_eligibility(rows, allowed_distribution_frequencies=("quarterly",))
    reverse = apply_eligibility(tuple(reversed(rows)), allowed_distribution_frequencies=("quarterly",))
    assert forward == reverse
    assert [row.listing.isin for row in forward.eligible] == ["GOOD"]
    assert [reason for _, reason in forward.rejected] == [
        DecisionReasonCode.DISTRIBUTION_NOT_ALLOWED,
        DecisionReasonCode.DATA_UNAVAILABLE,
        DecisionReasonCode.INSUFFICIENT_HISTORY,
    ]


def test_pr270_pareto_selects_non_dominated_front_and_extends_whole_rank() -> None:
    best = _row("BEST", annual_return=0.10, sharpe=1.4, sortino=1.6, volatility=0.08, expected_shortfall=0.02, drawdown=-0.05)
    tradeoff = _row("TRADEOFF", annual_return=0.12, sharpe=1.1, sortino=1.2, volatility=0.12, expected_shortfall=0.03, drawdown=-0.08)
    dominated = _row("DOMINATED", annual_return=0.05, sharpe=0.5, sortino=0.6, volatility=0.2, expected_shortfall=0.08, drawdown=-0.2)
    result = select_pareto((dominated, tradeoff, best), minimum_size=2)
    assert {member.listing.isin for member in result.selected} == {"BEST", "TRADEOFF"}
    assert [member.listing.isin for member in result.dominated] == ["DOMINATED"]


def test_pr270_stage_evidence_emits_decisions_and_before_after_snapshots() -> None:
    rows = (
        _row("A", annual_return=0.10, sharpe=1.4, sortino=1.6, volatility=0.08, expected_shortfall=0.02, drawdown=-0.05),
        _row("B", annual_return=None, sharpe=1.0, sortino=1.0, volatility=0.1, expected_shortfall=0.03, drawdown=-0.1),
    )
    eligibility = apply_eligibility(rows)
    eligibility_stage = eligibility_evidence(
        run_id="run-1",
        objective="return_risk",
        project_slug="alpha",
        pinned_revision="bi-1",
        rows=rows,
        result=eligibility,
        algorithm_version="algo-v1",
        profile_version="profile-v1",
    )
    assert eligibility_stage.decision.stage is DecisionStageId.INPUT_ELIGIBILITY
    assert eligibility_stage.before_snapshot.listing_count == 2
    assert eligibility_stage.after_snapshot.listing_count == 1
    assert eligibility_stage.after_snapshot.removed_count == 1

    pareto = select_pareto(eligibility.eligible)
    pareto_stage = pareto_evidence(
        run_id="run-1",
        objective="return_risk",
        project_slug="alpha",
        pinned_revision="bi-1",
        rows=eligibility.eligible,
        result=pareto,
        algorithm_version="algo-v1",
        profile_version="profile-v1",
    )
    assert pareto_stage.decision.stage is DecisionStageId.UNIVARIATE_PARETO
    assert pareto_stage.after_snapshot.listing_count == 1
