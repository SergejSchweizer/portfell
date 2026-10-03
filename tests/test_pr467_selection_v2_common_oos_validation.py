from __future__ import annotations

from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    COMPARISON_WALK_FORWARD_POLICY,
    build_common_oos_validation,
    build_split_candidate_families,
    build_split_risk_model_bundles,
)


def _families():
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    return rows, families


def test_common_oos_rows_measure_all_configs_on_identical_boundaries() -> None:
    rows, families = _families()
    validation = build_common_oos_validation(return_rows=rows, families=families)
    assert validation
    assert len(validation) == len(families) * 14
    boundaries = {
        (item.train_start, item.train_end, item.test_start, item.test_end) for item in validation
    }
    assert len(boundaries) == len(families)
    for family in families:
        expected = (family.train_start, family.train_end, family.test_start, family.test_end)
        split_rows = [item for item in validation if item.test_start == family.test_start]
        assert len(split_rows) == 14
        assert all(
            (item.train_start, item.train_end, item.test_start, item.test_end) == expected
            for item in split_rows
        )
        assert all(
            item.test_observation_count == COMPARISON_WALK_FORWARD_POLICY.test_window_observations
            for item in split_rows
        )


def test_common_oos_validation_preserves_configuration_lineage_and_unavailable_rows() -> None:
    rows, families = _families()
    validation = build_common_oos_validation(return_rows=rows, families=families)
    assert all(item.candidate_configuration_id for item in validation)
    assert all(item.risk_model_id for item in validation)
    assert all(item.risk_model_spec_id for item in validation)
    assert all(item.fit_calendar_id for item in validation)
    assert {item.test_start for item in validation} == {family.test_start for family in families}
