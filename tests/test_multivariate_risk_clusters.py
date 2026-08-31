from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import (
    CLUSTER_DISTANCE_CUT,
    build_hierarchical_risk_clusters,
)

A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")
C = MultivariateListingKey("IE3", "X", "C")


def test_average_linkage_does_not_chain_threshold_neighbors() -> None:
    result = build_hierarchical_risk_clusters(
        listings=(A, B, C),
        correlation=((1.0, 0.75, 0.20), (0.75, 1.0, 0.75), (0.20, 0.75, 1.0)),
    )
    assert result.available
    labels = {row.listing: row.cluster_id for row in result.memberships}
    assert len(set(labels.values())) == 2
    assert not (labels[A] == labels[B] == labels[C])


def test_cluster_labels_and_redundancy_ties_are_deterministic() -> None:
    result = build_hierarchical_risk_clusters(
        listings=(C, A, B),
        correlation=((1.0, 0.1, 0.1), (0.1, 1.0, 0.8), (0.1, 0.8, 1.0)),
    )
    assert result.available
    labels = {row.listing: row.cluster_id for row in result.memberships}
    assert labels[A] == labels[B] == "Cluster 1"
    assert labels[C] == "Cluster 2"
    warning = result.largest_redundancy_warning
    assert warning is not None
    assert (warning.left, warning.right, warning.correlation) == (A, B, 0.8)


def test_cluster_cut_is_frozen_in_correlation_distance() -> None:
    assert CLUSTER_DISTANCE_CUT > 0.0
    exactly = build_hierarchical_risk_clusters(
        listings=(A, B), correlation=((1.0, 0.70), (0.70, 1.0))
    )
    assert exactly.cluster_count == 1


def test_invalid_correlation_fails_closed() -> None:
    result = build_hierarchical_risk_clusters(listings=(A, B), correlation=((1.0, 1.1), (1.1, 1.0)))
    assert not result.available
    assert result.memberships == ()
