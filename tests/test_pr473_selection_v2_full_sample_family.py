from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    build_current_sample_candidate_family,
    build_risk_model_comparison,
)


def test_current_sample_family_has_exact_fourteen_slots_and_three_shared_models() -> None:
    snapshot, rows = _fixture()
    family = build_current_sample_candidate_family(snapshot=snapshot, return_rows=rows, income={})
    assert len(family.candidates) == 14
    assert tuple(key for key, _ in family.risk_models) == ("LW_FULL", "LW_ROLLING_252", "EWMA_094")
    assert all(candidate.fit_calendar_id for candidate in family.candidates)
    assert all(candidate.risk_model_id for candidate in family.candidates)
    assert {candidate.risk_model_spec_key for candidate in family.candidates} == {
        "LW_FULL",
        "LW_ROLLING_252",
        "EWMA_094",
    }
    assert len({candidate.candidate_configuration_id for candidate in family.candidates}) == 14


def test_same_method_specs_coexist_in_descriptive_family() -> None:
    snapshot, rows = _fixture()
    family = build_current_sample_candidate_family(snapshot=snapshot, return_rows=rows, income={})
    inverse = [
        candidate for candidate in family.candidates if candidate.method == "inverse_volatility"
    ]
    assert len(inverse) == 3
    assert len({candidate.candidate_id for candidate in inverse}) == 3
    assert len({candidate.risk_model_spec_id for candidate in inverse}) == 3
    assert all(row["evidence_role"] == "descriptive" for row in family.to_rows())


def test_comparison_materializes_current_sample_lineage_separately_from_ranking() -> None:
    snapshot, rows = _fixture()
    result = build_risk_model_comparison(snapshot=snapshot, return_rows=rows, income={})
    assert len(result["configuration_rankings"]["return_risk"]) == 14
    assert all(
        item["evidence_role"] == "selection"
        for item in result["configuration_rankings"]["return_risk"]
    )
