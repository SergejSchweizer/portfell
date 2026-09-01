from pathlib import Path

from portfell.univariate_distributions import build_metric_distributions
from portfell.univariate_metric_catalog import METRIC_IDS


def test_every_catalog_metric_has_reconcilable_distribution_evidence() -> None:
    rows = [
        {
            metric: ("monthly" if metric == "distribution_frequency" else 1.0)
            for metric in METRIC_IDS
        },
        {
            metric: ("quarterly" if metric == "distribution_frequency" else None)
            for metric in METRIC_IDS
        },
    ]
    result = build_metric_distributions(rows)
    assert set(result["metrics"]) == set(METRIC_IDS)
    assert result["item_count"] == 2
    for metric in METRIC_IDS:
        evidence = result["metrics"][metric]
        assert evidence["available"] + evidence["unavailable"] == 2


def test_closeout_evidence_freezes_qa_scope() -> None:
    text = (
        Path(__file__).parents[1] / "docs/evidence/univariate-income-dashboard-v1.md"
    ).read_text()
    for marker in (
        "20:00 Europe/Vienna",
        "univariate.metric_distributions@v1",
        "60% plot / 30% summary / 10% selector",
        "1440×900",
        "1024×768",
        "390×844",
        "exact 40-hex",
        "no credentials",
    ):
        assert marker in text
