from pathlib import Path

CONTRACT = Path("docs/contracts/multivariate-structure-v2.md")
BACKLOG = Path("BACKLOG.md")


def test_structure_v2_contract_freezes_artifacts_and_retired_names() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "multivariate.structure@v3" in text
    assert "multivariate.candidate_structure@v2" in text
    assert "covariance_effective_rank" in text
    assert "correlation_effective_rank" in text
    assert "signal_component_count" in text
    assert "effective_pca_risk_drivers" in text
    assert "does not emit `effective_independent_drivers`" in text
    assert "does not emit `strongest_common_driver`" in text


def test_structure_v2_contract_freezes_numerical_parameters() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for token in (
        "`0.80`, `0.90`, `0.95`",
        "sqrt((1 - 0.70) / 2)",
        "numpy.random.Generator(numpy.random.PCG64(41))",
        "exactly `100` null replicates",
        "quantile method `higher`",
        "exactly `252` aligned daily observations",
        "stride exactly `21` observations",
        "`24` most recent windows",
        "exactly `100` circular moving-block bootstrap replicates",
        "block length exactly `21`",
        "squared_frobenius_norm(U_prev^T * U_curr) / k",
    ):
        assert token in text


def test_structure_v2_contract_matches_authoritative_backlog_series() -> None:
    backlog = BACKLOG.read_text(encoding="utf-8")
    assert "## 7. Multivariate structural-risk analysis v2 — PR361–PR376" in backlog
    assert "PR365 + PR366 + PR368 + PR370 + PR371 -> PR372" in backlog
    assert "PR373 + PR374 + PR375 -> PR376(QA)" in backlog
