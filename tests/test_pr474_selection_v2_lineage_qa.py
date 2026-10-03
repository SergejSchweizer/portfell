from migration_evidence import full_sample_lineage_evidence
from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.app_services.multivariate_compute import _select_common_oos_decision
from portfell.multivariate_risk_model_comparison import build_current_sample_candidate_family


def test_current_sample_family_has_no_orphan_lineage_and_roles() -> None:
    snapshot, rows = _fixture()
    family = build_current_sample_candidate_family(snapshot=snapshot, return_rows=rows, income={})
    family_rows = list(family.to_rows())
    assert len(family_rows) == 14
    assert all(
        row["configuration_id"]
        and row["candidate_id"]
        and row["risk_model_id"]
        and row["fit_calendar_id"]
        for row in family_rows
    )
    assert all(row["evidence_role"] == "descriptive" for row in family_rows)
    inverse = [row for row in family_rows if row["method"] == "inverse_volatility"]
    assert len({row["spec_id"] for row in inverse}) == 3


def test_exact_winner_joins_to_one_current_candidate() -> None:
    snapshot, rows = _fixture()
    family = build_current_sample_candidate_family(snapshot=snapshot, return_rows=rows, income={})
    winner = family.candidates[1]
    comparison = {
        "configuration_rankings": {
            "return_risk": [
                {
                    "configuration_id": winner.candidate_configuration_id,
                    "method": winner.method,
                    "spec_key": winner.risk_model_spec_key,
                    "spec_id": winner.risk_model_spec_id,
                    "objective_score": 1.0,
                    "completed_split_count": 3,
                }
            ]
        }
    }
    decision = _select_common_oos_decision(
        objective="return_risk",
        risk_model_comparison=comparison,
        current_sample_candidates=family.candidates,
    )
    assert decision.available
    joined = [
        row
        for row in family.to_rows()
        if row["configuration_id"] == decision.document["winning_configuration_id"]
    ]
    assert len(joined) == 1
    assert joined[0]["candidate_id"] == decision.winning_candidate_id
    evidence = full_sample_lineage_evidence(
        sha="test-sha",
        family_rows=list(family.to_rows()),
        decision=decision.document,
        focused_tests=["test_pr474_selection_v2_lineage_qa.py"],
    )
    assert evidence["winner_joinable"] and evidence["winner_has_candidate_risk_fit"]
    assert evidence["status"] == "PASS"


def test_descriptive_artifact_mutation_is_outside_ranking_input() -> None:
    snapshot, rows = _fixture()
    family = build_current_sample_candidate_family(snapshot=snapshot, return_rows=rows, income={})
    ranking = {
        "configuration_rankings": {
            "minimum_risk": [
                {
                    "configuration_id": family.candidates[0].candidate_configuration_id,
                    "method": family.candidates[0].method,
                    "spec_key": "LW_FULL",
                    "spec_id": "spec",
                    "objective_score": -0.1,
                    "completed_split_count": 3,
                }
            ]
        }
    }
    first = _select_common_oos_decision(
        objective="minimum_risk",
        risk_model_comparison=ranking,
        current_sample_candidates=family.candidates,
    )
    ranking["current_sample_performance"] = [{"objective_score": 99999}]
    second = _select_common_oos_decision(
        objective="minimum_risk",
        risk_model_comparison=ranking,
        current_sample_candidates=family.candidates,
    )
    assert first.document == second.document
