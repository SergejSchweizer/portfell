from __future__ import annotations

import pytest

from portfell.multivariate.contracts.common import EvidenceAvailability, ListingIdentity
from portfell.multivariate.contracts.history import (
    RESEARCH_STAGE_ORDER,
    HistoryRange,
    ResearchStage,
    ResearchUniverseSnapshot,
)
from portfell.multivariate.contracts.project_selection import ProjectSelection


def test_pr283_research_stage_order_is_exact() -> None:
    assert RESEARCH_STAGE_ORDER == (
        ResearchStage.METADATA,
        ResearchStage.UNIVARIATE,
        ResearchStage.BIVARIATE,
        ResearchStage.MULTIVARIATE,
        ResearchStage.FINAL_PORTFOLIO,
    )


def test_pr283_observed_envelope_is_structurally_distinct_from_common_usable_history() -> None:
    snapshot = ResearchUniverseSnapshot(
        project_slug="alpha",
        revision="rev-1",
        stage=ResearchStage.MULTIVARIATE,
        availability=EvidenceAvailability.AVAILABLE,
        listing_count=12,
        unique_isin_count=11,
        removed_count=2,
        observed_history_envelope=HistoryRange("2018-01-02", "2026-08-19", 2100),
        common_usable_history=HistoryRange("2020-03-02", "2026-08-19", 1600),
    )
    assert snapshot.observed_history_envelope != snapshot.common_usable_history
    assert snapshot.observed_history_envelope.first_date == "2018-01-02"
    assert snapshot.common_usable_history.first_date == "2020-03-02"


def test_pr283_unavailable_history_never_carries_guessed_dates() -> None:
    with pytest.raises(ValueError, match="guessed dates"):
        HistoryRange("2020-01-01", None, None)


def test_pr283_snapshot_identity_is_mapping_order_invariant() -> None:
    common = dict(
        project_slug="alpha",
        revision="rev-1",
        stage=ResearchStage.UNIVARIATE,
        availability=EvidenceAvailability.AVAILABLE,
        listing_count=10,
        unique_isin_count=10,
        removed_count=2,
        observed_history_envelope=HistoryRange("2020-01-02", "2026-08-19", 1600),
        common_usable_history=HistoryRange("2021-01-04", "2026-08-19", 1400),
    )
    first = ResearchUniverseSnapshot(removal_reasons={"missing": 1, "frequency": 1}, **common)
    second = ResearchUniverseSnapshot(removal_reasons={"frequency": 1, "missing": 1}, **common)
    assert first.snapshot_id == second.snapshot_id


def test_pr283_project_selection_is_order_invariant_but_project_scoped() -> None:
    listings = (
        ListingIdentity("DE000A", "XETRA", "AAA"),
        ListingIdentity("DE000B", "XETRA", "BBB"),
    )
    alpha = ProjectSelection("alpha", "bi-1", listings)
    alpha_reversed = ProjectSelection("alpha", "bi-1", tuple(reversed(listings)))
    beta = ProjectSelection("beta", "bi-1", listings)
    assert alpha.selection_revision == alpha_reversed.selection_revision
    assert alpha.selection_revision != beta.selection_revision


def test_pr283_duplicate_full_listing_identity_is_rejected() -> None:
    listing = ListingIdentity("DE000A", "XETRA", "AAA")
    with pytest.raises(ValueError, match="duplicate listings"):
        ProjectSelection("alpha", "bi-1", (listing, listing))
