from migration_evidence import decision_authority_evidence

from portfell.app_services.multivariate_compute import _select_common_oos_decision


def _ranking(objective: str, winner: str = "cfg-a"):
    return {
        "configuration_rankings": {
            objective: [
                {
                    "configuration_id": winner,
                    "method": "inverse_volatility",
                    "spec_key": "EWMA_094",
                    "spec_id": "spec-ewma",
                    "objective_score": 1.0,
                    "completed_split_count": 3,
                }
            ]
        }
    }


def test_each_objective_reaches_the_same_single_authority() -> None:
    results = {}
    for objective in ("return_risk", "return_drawdown", "minimum_risk"):
        result = _select_common_oos_decision(
            objective=objective, risk_model_comparison=_ranking(objective)
        )
        results[objective] = result.document
        assert result.document["selection_authority"] == "common_oos_14_config"
        assert result.document["winning_configuration_id"] == "cfg-a"
        assert result.document["objective"] == objective
    evidence = decision_authority_evidence(
        sha="test-sha",
        objective_results=results,
        focused_tests=["test_pr472_selection_v2_decision_authority_qa.py"],
    )
    assert evidence["all_objectives_preserved"]
    assert evidence["legacy_ranking_reachable"] is False
    assert evidence["status"] == "PASS"


def test_legacy_or_descriptive_mutation_cannot_change_authority_input() -> None:
    ranking = _ranking("return_risk")
    baseline = _select_common_oos_decision(objective="return_risk", risk_model_comparison=ranking)
    ranking["legacy_scorecards"] = [{"objective_score": 999999}]
    changed = _select_common_oos_decision(objective="return_risk", risk_model_comparison=ranking)
    assert changed.document == baseline.document
