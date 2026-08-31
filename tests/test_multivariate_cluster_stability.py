import pytest

from portfell.multivariate_cluster_stability import (
    BOOTSTRAP_BLOCK_LENGTH,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    build_cluster_bootstrap_stability,
)
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import RiskClusterDiagnostics, RiskClusterMembership


A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")


def test_cluster_bootstrap_contract_constants_are_frozen() -> None:
    assert (BOOTSTRAP_REPLICATES, BOOTSTRAP_BLOCK_LENGTH, BOOTSTRAP_SEED) == (100, 21, 41)


def test_duplicate_series_pair_is_always_co_clustered_when_numpy_available() -> None:
    pytest.importorskip("numpy")
    rows = tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": f"2025-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
            "return": ((index % 9) - 4) * 0.001,
        }
        for index in range(80)
        for listing in (A, B)
    )
    canonical = RiskClusterDiagnostics(
        (RiskClusterMembership(A, "Cluster 1"), RiskClusterMembership(B, "Cluster 1")), 1, None, ()
    )
    result = build_cluster_bootstrap_stability(return_rows=rows, listings=(A, B), canonical_clusters=canonical)
    assert result.available
    assert result.pairs[0].co_cluster_probability == 1.0
    assert result.clusters[0].mean_co_cluster_probability == 1.0


def test_singleton_cluster_stability_is_not_fabricated_as_one() -> None:
    singleton = RiskClusterDiagnostics((RiskClusterMembership(A, "Cluster 1"),), 1, None, ())
    pytest.importorskip("numpy")
    rows = tuple(
        {"isin": A.isin, "exchange": A.exchange, "code": A.code, "date": f"d{index:03d}", "return": index * 0.001}
        for index in range(30)
    )
    result = build_cluster_bootstrap_stability(return_rows=rows, listings=(A,), canonical_clusters=singleton)
    assert result.available
    assert result.clusters[0].mean_co_cluster_probability is None
    assert result.clusters[0].availability_reasons == ("cluster_stability_not_applicable_singleton",)
