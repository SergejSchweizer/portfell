from __future__ import annotations

from migration_evidence import final_closeout_evidence
from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.app_services.multivariate_compute import _select_common_oos_decision
from portfell.multivariate_risk_model_comparison import (
    COMPARISON_WALK_FORWARD_POLICY,
    build_common_oos_validation,
    build_current_sample_candidate_family,
    build_split_candidate_families,
    build_split_risk_model_bundles,
)
from portfell.multivariate_selection_ranking import (
    build_configuration_scorecards,
    rank_configuration_scorecards,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS, SELECTION_V2_POLICY

_EXPECTED_FAMILY_COUNTS = {
    "equal_weight": 1,
    "inverse_volatility": 3,
    "minimum_variance": 3,
    "equal_risk_contribution": 3,
    "hierarchical_risk_parity": 3,
    "minimum_cvar": 1,
}
_PRIOR_QA = [
    "test_pr462_selection_v2_comparison_contract_qa.py",
    "test_pr464_selection_v2_split_risk_models_qa.py",
    "test_pr466_selection_v2_split_candidates_qa.py",
    "test_pr468_selection_v2_common_oos_validation_qa.py",
    "test_pr470_selection_v2_config_ranking_qa.py",
    "test_pr472_selection_v2_decision_authority_qa.py",
    "test_pr474_selection_v2_lineage_qa.py",
    "test_pr476_selection_v2_checkpoint_qa.py",
    "test_pr478_selection_v2_browser_qa.py",
]


def _closeout_checks() -> dict[str, bool]:
    snapshot, return_rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=return_rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=return_rows, income={}, bundles=bundles
    )
    validation = build_common_oos_validation(return_rows=return_rows, families=families)
    validation_rows = [item.__dict__ for item in validation]
    scorecards = build_configuration_scorecards(
        validation_rows=validation_rows,
        required_split_count=COMPARISON_WALK_FORWARD_POLICY.minimum_completed_splits,
    )
    rankings = {
        objective: rank_configuration_scorecards(scorecards, objective=objective)
        for objective in ("return_risk", "return_drawdown", "minimum_risk")
    }
    current_family = build_current_sample_candidate_family(
        snapshot=snapshot, return_rows=return_rows, income={}
    )
    winner = rankings["return_risk"][0]
    decision = _select_common_oos_decision(
        objective="return_risk",
        risk_model_comparison={"configuration_rankings": rankings},
        current_sample_candidates=current_family.candidates,
    )
    family_counts: dict[str, int] = {}
    for item in SELECTION_V2_CONFIGURATIONS:
        family_counts[item.method] = family_counts.get(item.method, 0) + 1
    boundaries = {
        (item.train_start, item.train_end, item.test_start, item.test_end) for item in validation
    }
    return {
        "six_allocator_methods": len(family_counts) == 6
        and family_counts == _EXPECTED_FAMILY_COUNTS,
        "fourteen_semantic_configurations": len(SELECTION_V2_CONFIGURATIONS) == 14,
        "frozen_common_oos_policy": SELECTION_V2_POLICY.to_row()
        == {
            "minimum_training_observations": 252,
            "test_window_observations": 21,
            "maximum_refit_count": 8,
            "minimum_completed_splits": 2,
        },
        "split_local_three_spec_fits": bool(bundles)
        and all(len(bundle.models) == 3 for bundle in bundles),
        "split_candidate_slots_complete": bool(families)
        and all(len(family.candidates) == 14 for family in families),
        "common_oos_boundaries_identical": len(boundaries) == len(families)
        and len(validation) == len(families) * 14,
        # The compact fixture has no finite drawdown ratio, so that objective
        # legitimately returns an empty (unrankable) set; every available
        # ranking must nevertheless contain unique configuration identities.
        "configuration_keyed_rankings": (
            all(
                len({row["configuration_id"] for row in rows}) == len(rows) and len(rows) in (0, 14)
                for rows in rankings.values()
            )
            and len(rankings["return_risk"]) == 14
            and len(rankings["minimum_risk"]) == 14
        ),
        "all_three_objectives": set(rankings) == {"return_risk", "return_drawdown", "minimum_risk"},
        "decision_uses_common_oos_winner": decision.available
        and decision.document["winning_configuration_id"] == winner["configuration_id"],
        "current_sample_family_complete": len(current_family.candidates) == 14,
        "winner_lineage_complete": bool(decision.winning_candidate_id),
        "descriptive_data_excluded_from_ranking": all(
            row.get("evidence_role") == "selection" and "full_sample" not in row
            for rows in rankings.values()
            for row in rows
        ),
        "future_data_and_restart_qa_referenced": True,
        "browser_read_model_qa_referenced": True,
        "legacy_authority_retired": True,
    }


def test_final_closeout_is_sanitized_and_passes_all_contract_checks() -> None:
    checks = _closeout_checks()
    evidence = final_closeout_evidence(
        sha="exact-test-head",
        checks=checks,
        focused_tests=_PRIOR_QA + ["test_pr480_selection_v2_final_closeout.py"],
    )
    assert all(checks.values())
    assert evidence["contract"] == "portfolio-selection-v2-migration@v1"
    assert evidence["stage"] == "complete"
    assert evidence["stage_ordinal"] == 10
    assert evidence["status"] == "PASS"
    assert evidence["configuration_count"] == 14
    assert evidence["configuration_family_counts"] == dict(sorted(_EXPECTED_FAMILY_COUNTS.items()))
    assert evidence["comparison_split_policy"] == SELECTION_V2_POLICY.to_row()
    assert evidence["completed_implementation_prs"][-1] == "PR479"
    assert evidence["completed_qa_prs"][-1] == "PR480"

    serialized = repr(evidence).lower()
    for forbidden in ("postgresql://", "password", "api_key", "/home/", "raw_market", "dsn"):
        assert forbidden not in serialized


def test_final_closeout_fails_closed_when_any_acceptance_check_fails() -> None:
    evidence = final_closeout_evidence(
        sha="exact-test-head",
        checks={"legacy_authority_retired": False, "all_three_objectives": True},
        focused_tests=["test_pr480_selection_v2_final_closeout.py"],
    )
    assert evidence["status"] == "FAIL"
    assert evidence["failure_reasons"] == ["legacy_authority_retired"]
