from math import sqrt

from portfell.multivariate_subspace_stability import build_adjacent_subspace_stability, subspace_overlap


def test_subspace_overlap_is_sign_and_rotation_invariant() -> None:
    identity = ((1.0, 0.0), (0.0, 1.0))
    signed = ((-1.0, 0.0), (0.0, -1.0))
    angle = 1 / sqrt(2)
    rotated = ((angle, angle), (-angle, angle))
    assert subspace_overlap(identity, signed, component_count=2) == 1.0
    assert subspace_overlap(identity, rotated, component_count=2) == 1.0


def test_orthogonal_one_dimensional_subspaces_score_zero() -> None:
    assert subspace_overlap(((1.0, 0.0),), ((0.0, 1.0),), component_count=1) == 0.0


def test_subspace_component_count_is_min_three_listing_count() -> None:
    rows = build_adjacent_subspace_stability(
        date_ends=("2025-01-01", "2025-02-01"),
        covariance_bases=(((1.0, 0.0), (0.0, 1.0)), ((1.0, 0.0), (0.0, 1.0))),
        correlation_bases=(((1.0, 0.0), (0.0, 1.0)), ((1.0, 0.0), (0.0, 1.0))),
        listing_count=2,
    )
    assert rows[0].component_count == 2
    assert rows[0].covariance_stability == 1.0


def test_fewer_than_two_windows_is_typed_unavailable() -> None:
    rows = build_adjacent_subspace_stability(
        date_ends=("2025-01-01",), covariance_bases=(((1.0,),),), correlation_bases=(((1.0,),),), listing_count=1
    )
    assert rows[0].availability_reasons == ("subspace_stability_insufficient_windows",)
