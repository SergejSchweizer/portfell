from __future__ import annotations

from portfell.multivariate.orchestration.hosted_bridge import select_hosted_oos_winner


def _candidate(candidate_id: str, weight: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "weights": [
            {"isin": "A", "exchange": "XETRA", "code": "AAA", "weight": weight},
            {"isin": "B", "exchange": "XETRA", "code": "BBB", "weight": 1.0 - weight},
        ],
    }


def _five_splits(candidate_id: str, sharpe: float) -> list[dict[str, object]]:
    ranges = (
        ("2024-03-29", "2024-04-01", "2024-04-30"),
        ("2024-04-30", "2024-05-01", "2024-05-31"),
        ("2024-05-31", "2024-06-03", "2024-06-28"),
        ("2024-06-28", "2024-07-01", "2024-07-31"),
        ("2024-07-31", "2024-08-01", "2024-08-30"),
    )
    return [
        {
            "kind": "walk_forward",
            "status": "complete",
            "candidate_id": candidate_id,
            "train_start": "2024-01-02",
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "test_observation_count": 21,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sharpe + 0.2,
            "max_drawdown": -0.08,
            "conditional_value_at_risk": 0.03,
            "turnover": 0.10,
            "post_cost_return": 0.01,
            "volatility": 0.10,
        }
        for train_end, test_start, test_end in ranges
    ]


def _select(candidates, validation):
    return select_hosted_oos_winner(
        run_id="run-1",
        settings={"objective": "return_risk"},
        summary={
            "aligned_period": {
                "date_start": "2024-01-02",
                "date_end": "2024-12-31",
                "observation_count": 252,
            }
        },
        candidates=candidates,
        validation=validation,
    )


def test_pr272_five_split_ranges_are_preserved_exactly() -> None:
    selected = _select(
        [_candidate("cfg-a", 0.6), _candidate("cfg-b", 0.4)],
        [*_five_splits("cfg-a", 1.3), *_five_splits("cfg-b", 0.9)],
    )
    assert len(selected.result.splits) == 5
    assert [split.split_id for split in selected.result.splits] == [
        "hosted-wf-01",
        "hosted-wf-02",
        "hosted-wf-03",
        "hosted-wf-04",
        "hosted-wf-05",
    ]
    assert selected.result.splits[-1].training_dates[-1] == "2024-07-31"
    assert selected.result.splits[-1].test_dates[0] == "2024-08-01"


def test_pr272_reversed_input_and_restart_produce_identical_logical_result() -> None:
    candidates = [_candidate("cfg-a", 0.6), _candidate("cfg-b", 0.4)]
    validation = [*_five_splits("cfg-a", 1.3), *_five_splits("cfg-b", 0.9)]
    first = _select(candidates, validation)
    restarted = _select(list(reversed(candidates)), list(reversed(validation)))
    assert first == restarted
    assert first.candidate_id == "cfg-a"
    assert first.result.final_refit.configuration_id == "cfg-a"
