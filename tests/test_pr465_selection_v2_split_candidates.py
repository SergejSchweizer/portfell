from __future__ import annotations

from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    build_split_candidate_families,
    build_split_risk_model_bundles,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS


def test_each_split_has_exactly_fourteen_joinable_candidate_slots() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows, starts=(100, 252))
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    assert families
    expected_ids = tuple(item.configuration_id for item in SELECTION_V2_CONFIGURATIONS)
    for family in families:
        assert (
            tuple(candidate.candidate_configuration_id for candidate in family.candidates)
            == expected_ids
        )
        assert len(family.candidates) == 14
        assert all(
            candidate.risk_model_id and candidate.fit_calendar_id for candidate in family.candidates
        )
        assert all(candidate.candidate_id for candidate in family.candidates)


def test_same_method_different_specs_are_not_overwritten() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    family = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles[:1]
    )[0]
    inverse = [
        candidate for candidate in family.candidates if candidate.method == "inverse_volatility"
    ]
    assert len(inverse) == 3
    assert len({candidate.candidate_configuration_id for candidate in inverse}) == 3
    assert len({candidate.risk_model_spec_key for candidate in inverse}) == 3


def test_candidate_slot_status_is_explicit_when_risk_fit_unavailable() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows, starts=(100, 252))
    family = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles[:1]
    )[0]
    rolling = [
        candidate
        for candidate in family.candidates
        if candidate.risk_model_spec_key == "LW_ROLLING_252"
    ]
    assert len(rolling) == 4
    assert all(candidate.status == "unavailable" for candidate in rolling)
    assert all(candidate.reasons for candidate in rolling)
