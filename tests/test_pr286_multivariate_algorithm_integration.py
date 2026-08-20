from __future__ import annotations

from portfell.multivariate.candidates.pipeline import build_candidate_universe
from portfell.multivariate.contracts.common import DecisionStageId, ListingIdentity
from portfell.multivariate.selector.eligibility import SelectorMetrics
from portfell.multivariate.selector.pipeline import SelectorEvidenceContext, select_optimizer_universe


def _selector_row(index: int) -> SelectorMetrics:
    return SelectorMetrics(
        listing=ListingIdentity(f"ISIN-{index:04d}", "XETRA", f"C{index:04d}"),
        annualized_geometric_return=0.08,
        sharpe=1.0,
        sortino=1.2,
        annualized_volatility=0.10,
        expected_shortfall=0.03,
        maximum_drawdown=-0.10,
        observation_count=500,
        distribution_frequency="quarterly",
    )


def _correlations(
    rows: tuple[SelectorMetrics, ...],
) -> dict[tuple[ListingIdentity, ListingIdentity], float]:
    listings = tuple(row.listing for row in rows)
    return {
        (listings[left], listings[right]): 0.4
        for left in range(len(listings))
        for right in range(left + 1, len(listings))
    }


def _context() -> SelectorEvidenceContext:
    return SelectorEvidenceContext(
        run_id="run-1",
        objective="return_risk",
        project_slug="alpha",
        pinned_revision="bi-1",
        algorithm_version="algo-v1",
        profile_version="profile-v1",
    )


def test_pr286_400_input_selector_is_stable_and_reduces_to_250_with_audit_chain() -> None:
    rows = tuple(_selector_row(index) for index in range(400))
    correlations = _correlations(rows)
    forward = select_optimizer_universe(
        rows,
        correlations=correlations,
        evidence_context=_context(),
        maximum_size=250,
    )
    reverse = select_optimizer_universe(
        tuple(reversed(rows)),
        correlations=correlations,
        evidence_context=_context(),
        maximum_size=250,
    )
    assert forward == reverse
    assert len(forward.selected) == 250
    assert [decision.stage for decision in forward.decisions] == [
        DecisionStageId.INPUT_ELIGIBILITY,
        DecisionStageId.UNIVARIATE_PARETO,
        DecisionStageId.BIVARIATE_REDUNDANCY,
    ]
    assert [snapshot.listing_count for snapshot in forward.snapshots] == [400, 400, 400, 250]


def test_pr286_candidate_pipeline_builds_all_three_by_seven_configurations_deterministically() -> None:
    listings = (
        ListingIdentity("A", "XETRA", "AAA"),
        ListingIdentity("B", "XETRA", "BBB"),
        ListingIdentity("C", "XETRA", "CCC"),
    )
    dates = tuple(f"2024-01-{day:02d}" for day in range(2, 12))
    series = {
        listing: tuple((date, 0.001 * (index + 1) + offset / 100000) for offset, date in enumerate(dates))
        for index, listing in enumerate(listings)
    }
    forward = build_candidate_universe(
        series,
        settings_version="settings-v1",
        algorithm_version="algo-v1",
        max_weight=0.8,
    )
    reverse = build_candidate_universe(
        dict(reversed(tuple(series.items()))),
        settings_version="settings-v1",
        algorithm_version="algo-v1",
        max_weight=0.8,
    )
    assert forward == reverse
    assert len(forward) == 21
    assert len({item.configuration.configuration_id for item in forward}) == 21
    assert all(item.candidate.available or item.candidate.reason for item in forward)
