from __future__ import annotations

import pytest

from portfell.hosted_research_service import ResearchService
from portfell.multivariate.orchestration.hosted_bridge import select_hosted_oos_winner


def _candidate(candidate_id: str, first_weight: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "weights": [
            {"isin": "A", "exchange": "XETRA", "code": "AAA", "weight": first_weight},
            {
                "isin": "B",
                "exchange": "XETRA",
                "code": "BBB",
                "weight": 1.0 - first_weight,
            },
        ],
    }


def _validation(
    candidate_id: str,
    *,
    sharpe: float,
    sortino: float,
    drawdown: float,
    cvar: float,
    turnover: float,
    post_cost_return: float,
    volatility: float,
) -> list[dict[str, object]]:
    return [
        {
            "kind": "walk_forward",
            "status": "complete",
            "candidate_id": candidate_id,
            "train_start": "2024-01-02",
            "train_end": "2024-06-28",
            "test_start": "2024-07-01",
            "test_end": "2024-07-31",
            "test_observation_count": 21,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": drawdown,
            "conditional_value_at_risk": cvar,
            "turnover": turnover,
            "post_cost_return": post_cost_return,
            "volatility": volatility,
        },
        {
            "kind": "walk_forward",
            "status": "complete",
            "candidate_id": candidate_id,
            "train_start": "2024-01-02",
            "train_end": "2024-07-31",
            "test_start": "2024-08-01",
            "test_end": "2024-08-30",
            "test_observation_count": 22,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": drawdown,
            "conditional_value_at_risk": cvar,
            "turnover": turnover,
            "post_cost_return": post_cost_return,
            "volatility": volatility,
        },
    ]


def _summary() -> dict[str, object]:
    return {
        "aligned_period": {
            "date_start": "2024-01-02",
            "date_end": "2024-12-31",
            "observation_count": 252,
        }
    }


def test_return_risk_selects_only_from_walk_forward_oos_and_uses_full_refit_weights() -> None:
    candidates = [_candidate("cfg-a", 0.7), _candidate("cfg-b", 0.4)]
    validation = [
        *_validation(
            "cfg-a",
            sharpe=1.4,
            sortino=1.7,
            drawdown=-0.12,
            cvar=0.04,
            turnover=0.20,
            post_cost_return=0.02,
            volatility=0.16,
        ),
        *_validation(
            "cfg-b",
            sharpe=0.9,
            sortino=1.1,
            drawdown=-0.08,
            cvar=0.03,
            turnover=0.10,
            post_cost_return=0.03,
            volatility=0.11,
        ),
        {
            "kind": "stress",
            "status": "complete",
            "candidate_id": "cfg-b",
            "sharpe_ratio": 99.0,
        },
    ]

    selected = select_hosted_oos_winner(
        run_id="run-1",
        settings={"objective": "return_risk"},
        summary=_summary(),
        candidates=candidates,
        validation=validation,
    )

    assert selected.candidate_id == "cfg-a"
    assert selected.result.winner.configuration_id == "cfg-a"
    assert selected.result.final_refit.configuration_id == "cfg-a"
    assert selected.result.final_refit.weights == pytest.approx((0.7, 0.3))
    assert selected.result.final_refit.first_date == "2024-01-02"
    assert selected.result.final_refit.last_date == "2024-12-31"
    assert selected.result.final_refit.observation_count == 252
    split_boundaries = [
        (split.training_dates[-1], split.test_dates[0]) for split in selected.result.splits
    ]
    assert split_boundaries == [
        ("2024-06-28", "2024-07-01"),
        ("2024-07-31", "2024-08-01"),
    ]


@pytest.mark.parametrize(
    ("objective", "expected"),
    [
        ("return_drawdown", "cfg-return"),
        ("minimum_risk", "cfg-risk"),
    ],
)
def test_objective_specific_oos_ranking_is_used(objective: str, expected: str) -> None:
    candidates = [_candidate("cfg-return", 0.6), _candidate("cfg-risk", 0.5)]
    validation = [
        *_validation(
            "cfg-return",
            sharpe=1.0,
            sortino=1.0,
            drawdown=-0.08,
            cvar=0.04,
            turnover=0.2,
            post_cost_return=0.04,
            volatility=0.20,
        ),
        *_validation(
            "cfg-risk",
            sharpe=1.0,
            sortino=1.0,
            drawdown=-0.05,
            cvar=0.02,
            turnover=0.1,
            post_cost_return=0.01,
            volatility=0.08,
        ),
    ]

    selected = select_hosted_oos_winner(
        run_id="run-1",
        settings={"objective": objective},
        summary=_summary(),
        candidates=candidates,
        validation=validation,
    )

    assert selected.candidate_id == expected


def test_missing_complete_oos_evidence_fails_closed_without_fabricating_winner() -> None:
    with pytest.raises(ValueError, match="no OOS candidate evidence"):
        select_hosted_oos_winner(
            run_id="run-1",
            settings={"objective": "return_risk"},
            summary=_summary(),
            candidates=[_candidate("cfg-a", 0.7)],
            validation=[
                {"kind": "stress", "status": "complete", "candidate_id": "cfg-a"}
            ],
        )


class _Multivariate:
    def __init__(self) -> None:
        self.selected: tuple[str, ...] | None = None

    def complete(self, user_id: str, run_id: str) -> None:
        assert (user_id, run_id) == ("user-1", "run-1")

    def status(self, user_id: str, run_id: str):
        return {"status": "complete", "settings": {"objective": "return_risk"}}

    def candidates(self, user_id: str, run_id: str):
        return {"items": [_candidate("cfg-a", 0.7), _candidate("cfg-b", 0.4)]}

    def validation(self, user_id: str, run_id: str):
        return {
            "items": [
                *_validation(
                    "cfg-a",
                    sharpe=1.5,
                    sortino=1.6,
                    drawdown=-0.10,
                    cvar=0.04,
                    turnover=0.2,
                    post_cost_return=0.02,
                    volatility=0.15,
                ),
                *_validation(
                    "cfg-b",
                    sharpe=0.8,
                    sortino=0.9,
                    drawdown=-0.05,
                    cvar=0.02,
                    turnover=0.1,
                    post_cost_return=0.01,
                    volatility=0.08,
                ),
            ]
        }

    def summary(self, user_id: str, run_id: str):
        return _summary()

    def update_settings(
        self,
        user_id: str,
        run_id: str,
        selected_candidate_ids: tuple[str, ...],
    ):
        self.selected = selected_candidate_ids
        return {"selected_candidate_ids": list(selected_candidate_ids)}


class _Unused:
    pass


def test_research_service_publishes_exactly_the_oos_selected_candidate() -> None:
    multivariate = _Multivariate()
    service = ResearchService(  # type: ignore[arg-type]
        _Unused(), _Unused(), multivariate, _Unused()
    )

    service.complete_multivariate("user-1", "run-1")

    assert multivariate.selected == ("cfg-a",)
