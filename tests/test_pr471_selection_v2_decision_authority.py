from types import SimpleNamespace

from portfell.app_services.multivariate_compute import _select_common_oos_decision


def _comparison(objective="return_risk"):
    return {
        "configuration_rankings": {
            objective: [
                {
                    "rank": 1,
                    "configuration_id": "cfg-ewma",
                    "method": "inverse_volatility",
                    "spec_key": "EWMA_094",
                    "spec_id": "spec-ewma",
                    "objective_score": 1.25,
                    "completed_split_count": 3,
                    "median_turnover": 0.1,
                    "median_herfindahl_index": 0.2,
                }
            ]
        }
    }


def test_decision_uses_common_oos_configuration_and_exact_objective() -> None:
    for objective in ("return_risk", "return_drawdown", "minimum_risk"):
        current = SimpleNamespace(
            candidate_configuration_id="cfg-ewma",
            candidate_id="candidate-current",
            status="feasible",
            risk_model_id="risk-ewma",
            fit_calendar_id="calendar-ewma",
        )
        result = _select_common_oos_decision(
            objective=objective,
            risk_model_comparison=_comparison(objective),
            current_sample_candidates=(current,),
        )
        assert result.available and result.production_eligible
        assert result.objective == objective
        assert result.winning_candidate_id == "candidate-current"
        assert result.document["selection_authority"] == "common_oos_14_config"
        assert result.document["risk_model_spec_key"] == "EWMA_094"


def test_unrankable_configuration_never_falls_back_to_legacy_candidate() -> None:
    result = _select_common_oos_decision(
        objective="return_risk",
        risk_model_comparison={"configuration_rankings": {"return_risk": []}},
    )
    assert not result.available
    assert result.winning_candidate_id == "unavailable"
    assert result.document["selection_authority"] == "common_oos_14_config"
    assert "fallback" not in str(result.document).lower()
