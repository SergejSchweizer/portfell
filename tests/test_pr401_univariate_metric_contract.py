from portfell.univariate_metric_catalog import METRIC_IDS, metric_catalog


def test_catalog_is_complete_and_unique() -> None:
    definitions = metric_catalog()
    assert len(definitions) == len(METRIC_IDS)
    assert len({item.metric_id for item in definitions}) == len(METRIC_IDS)
    assert {item.metric_id for item in definitions} == set(METRIC_IDS)
    assert all(item.unit and item.kind and item.filter_type for item in definitions)


def test_contract_documents_frozen_dashboard_semantics() -> None:
    from pathlib import Path

    text = (
        Path(__file__).parents[1] / "docs/contracts/univariate-income-metrics-v1.md"
    ).read_text()
    for marker in (
        "60% plot / 30% table / 10% controls",
        "Apply selection & compute downstream",
        "365.25",
        "invented FX",
    ):
        assert marker in text
