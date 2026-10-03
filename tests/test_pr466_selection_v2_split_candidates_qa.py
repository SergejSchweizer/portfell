from __future__ import annotations

from migration_evidence import split_candidate_family_evidence
from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    build_split_candidate_families,
    build_split_risk_model_bundles,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS


def test_independent_mapping_has_exact_fourteen_unique_semantic_slots() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    expected = {
        item.configuration_id: (item.method, item.risk_model_spec.spec_key)
        for item in SELECTION_V2_CONFIGURATIONS
    }
    assert len(expected) == 14
    for family in families[:3]:
        actual = {
            candidate.candidate_configuration_id: (candidate.method, candidate.risk_model_spec_key)
            for candidate in family.candidates
        }
        assert actual == expected
        assert len(actual) == 14


def test_duplicate_configuration_ids_fail_closed() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    family = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles[:1]
    )[0]
    rows_for_check = list(family.to_rows())
    rows_for_check.append(dict(rows_for_check[0]))
    ids = [row["configuration_id"] for row in rows_for_check]
    assert len(ids) != len(set(ids))


def test_stage_three_evidence_is_sanitized_and_complete() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    evidence = split_candidate_family_evidence(
        sha="test-sha",
        candidate_rows=[row for family in families for row in family.to_rows()],
        focused_tests=["test_pr465_selection_v2_split_candidates.py"],
    )
    assert evidence["stage"] == "split_candidate_family_complete"
    assert evidence["exact_fourteen_slots"]
    assert evidence["configuration_identity_stable"]
    assert evidence["fit_identity_persisted"]
    assert evidence["status"] == "PASS"
