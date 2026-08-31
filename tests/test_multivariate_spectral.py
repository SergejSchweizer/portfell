from math import isclose, sqrt

from portfell.multivariate_spectral import analyze_symmetric_matrix


def test_spectral_core_orders_components_and_freezes_thresholds() -> None:
    result = analyze_symmetric_matrix(((2.0, 0.0), (0.0, 1.0)))
    assert result.available
    assert result.eigenvalues == (2.0, 1.0)
    assert result.explained_variance == (2 / 3, 1 / 3)
    assert result.cumulative_explained_variance[-1] == 1.0
    assert result.components_for(0.8) == 2
    assert result.components_for(0.9) == 2
    assert result.components_for(0.95) == 2
    assert result.effective_rank is not None


def test_spectral_core_component_vectors_are_eigenvectors_and_sign_stable() -> None:
    result = analyze_symmetric_matrix(((2.0, 1.0), (1.0, 2.0)))
    assert result.available
    first = result.component_coefficients[0]
    expected = 1 / sqrt(2)
    assert isclose(first[0], expected, rel_tol=1e-9, abs_tol=1e-12)
    assert isclose(first[1], expected, rel_tol=1e-9, abs_tol=1e-12)
    assert result == analyze_symmetric_matrix(((2.0, 1.0), (1.0, 2.0)))


def test_spectral_core_clips_only_tiny_negative_eigenvalues() -> None:
    tiny = analyze_symmetric_matrix(((1.0, 0.0), (0.0, -5e-13)))
    assert tiny.available
    assert tiny.eigenvalues[-1] == 0.0
    invalid = analyze_symmetric_matrix(((1.0, 0.0), (0.0, -2e-12)))
    assert not invalid.available
    assert invalid.availability_reasons == ("spectral_negative_eigenvalue",)


def test_spectral_core_fails_closed_for_invalid_matrix() -> None:
    assert not analyze_symmetric_matrix(()).available
    assert not analyze_symmetric_matrix(((1.0, 2.0),)).available
    assert not analyze_symmetric_matrix(((1.0, 0.1), (0.2, 1.0))).available
