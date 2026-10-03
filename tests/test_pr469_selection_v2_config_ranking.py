from __future__ import annotations

from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    build_common_oos_validation,
    build_split_candidate_families,
    build_split_risk_model_bundles,
)
from portfell.multivariate_selection_ranking import (
    build_configuration_scorecards,
    rank_configuration_scorecards,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS


def _cards():
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    validation = build_common_oos_validation(return_rows=rows, families=families)
    rows = [item.__dict__ for item in validation]
    return rows, build_configuration_scorecards(
        validation_rows=rows,
        required_split_count=2,
    )


def test_scorecards_are_configuration_keyed_and_complete() -> None:
    rows, cards = _cards()
    assert len(cards) == 14
    assert tuple(card.configuration_id for card in cards) == tuple(
        item.configuration_id for item in SELECTION_V2_CONFIGURATIONS
    )
    assert all(card.completed_split_count == 3 for card in cards)
    assert all(card.rankable for card in cards)
    assert all(card.median_sharpe_ratio is not None for card in cards)


def test_ranking_is_deterministic_and_uses_only_selection_evidence() -> None:
    _, cards = _cards()
    first = rank_configuration_scorecards(cards, objective="return_risk")
    second = rank_configuration_scorecards(tuple(reversed(cards)), objective="return_risk")
    assert first == second
    assert [item["rank"] for item in first] == list(range(1, len(first) + 1))
    assert all(item["evidence_role"] == "selection" for item in first)
    assert all("full_sample" not in item for item in first)


def test_incomplete_configuration_is_unrankable_but_retained() -> None:
    rows, _ = _cards()
    config = rows[0]["candidate_configuration_id"]
    reduced = [
        row
        for row in rows
        if row["candidate_configuration_id"] == config
        and row["test_start"] == rows[0]["test_start"]
    ]
    remaining = [row for row in rows if row["candidate_configuration_id"] != config]
    cards = build_configuration_scorecards(
        validation_rows=remaining + reduced, required_split_count=3
    )
    card = next(item for item in cards if item.configuration_id == config)
    assert not card.rankable
    assert "incomplete_common_split_evidence" in card.availability_reasons
    assert config not in {
        item["configuration_id"]
        for item in rank_configuration_scorecards(cards, objective="return_risk")
    }


def test_ranking_rejects_invalid_objective() -> None:
    _, cards = _cards()
    try:
        rank_configuration_scorecards(cards, objective="full_sample")
    except ValueError as error:
        assert str(error) == "invalid_multivariate_objective"
    else:
        raise AssertionError("invalid objective was accepted")
