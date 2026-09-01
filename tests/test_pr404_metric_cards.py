from portfell.dash_app.metric_cards import metric_card_models
from portfell.univariate_metric_catalog import METRIC_IDS


def test_metric_card_registry_has_one_card_per_catalog_metric() -> None:
    cards = metric_card_models({"metrics": {metric: {} for metric in METRIC_IDS}})
    assert len(cards) == len(METRIC_IDS)
    assert {card["metric_id"] for card in cards} == set(METRIC_IDS)
    assert [cards[index]["group"] for index in (0, 4, 20, 31, 34)] == [
        "Data quality",
        "Income & distributions",
        "Return & capital risk",
        "Risk-adjusted return",
        "Robustness & distribution shape",
    ]
