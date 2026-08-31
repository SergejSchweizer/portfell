# Multivariate Structure v2 quantitative contract

Status: frozen for PR361–PR376. Production activation is gated by PR372 and by the merged PR360 production-cutover PASS evidence.

## 1. Invariants

The universe artifact is `multivariate.structure@v3`. The candidate artifact is `multivariate.candidate_structure@v2`. All structural outputs are diagnostics: they MUST NOT alter candidate feasibility, candidate weights, the frozen objectives (`return_risk`, `return_drawdown`, `minimum_risk`), OOS ranking, or the DecisionArtifact winner. HRP keeps its optimizer-internal clustering and MUST NOT consume v2 Risk Structure clusters.

Every result is derived from one immutable Multivariate input snapshot, its aligned daily log-return matrix, and the canonical production Ledoit-Wolf joint covariance artifact. No pairwise covariance/correlation, sample-covariance fallback, shorter rolling window, implicit zero, or weaker clustering fallback is permitted. Optional diagnostics fail closed with typed availability reasons.

V1 artifacts remain immutable historical data. New v2 production artifacts are published only when PR372 lands. V2 does not emit `effective_independent_drivers`. V2 does not emit `strongest_common_driver`.

## 2. Shared numerical contract

Absolute tolerance is `1e-12`; relative tolerance is `1e-9` unless a field states otherwise. Eigenvalues are sorted descending with deterministic stable tie handling. A numerical eigenvalue in `[-1e-12, 0)` is clipped to `0`; an eigenvalue `< -1e-12` makes that spectral result unavailable with reason `spectral_negative_eigenvalue`.

Each eigenvector is sign-normalized by locating the first coefficient in canonical listing order with absolute value `> 1e-12`; that coefficient is made positive. If all coefficients are within the tolerance, the vector is left unchanged. Canonical listing order is the exact order stored by the matching risk-model artifact; identity comparisons use full `(isin, exchange, code)` tuples.

For positive eigenvalues `lambda_i`, define shares `p_i = lambda_i / sum_j(lambda_j)`. Effective rank is exactly:

```text
exp(-sum(p_i * log(p_i) for p_i > 0))
```

Explained-variance thresholds are exactly `0.80`, `0.90`, `0.95`. `components_for_Xpct` is the smallest leading component count whose cumulative explained variance is at least the threshold.

## 3. Covariance PCA

Input is the canonical Ledoit-Wolf covariance matrix `Sigma`. Output fields are:

- `covariance_eigenvalues`: variance units, descending.
- `covariance_explained_variance`: dimensionless shares.
- `covariance_cumulative_explained_variance`: dimensionless cumulative shares.
- `covariance_effective_rank`: dimensionless entropy effective count.
- `covariance_components_for_80pct`, `covariance_components_for_90pct`, `covariance_components_for_95pct`: integer counts.
- `covariance_component_coefficients`: rows `(component_id, full listing identity, coefficient)` in component order then canonical listing order.
- `covariance_dominant_component_representative`: full listing identity with largest absolute Component-1 coefficient; ties resolve by canonical listing identity ascending.
- `covariance_dominant_component_share`: Component-1 explained-variance share.

A missing/unavailable risk model makes covariance PCA unavailable with `risk_model_unavailable`. Non-positive total eigenvalue mass yields `spectral_non_positive_total`.

## 4. Correlation PCA

For every listing `i`, canonical variance `Sigma_ii` must be finite and strictly positive. Then:

```text
R_ij = Sigma_ij / sqrt(Sigma_ii * Sigma_jj)
```

The diagonal is `1.0` within absolute tolerance `1e-12`. A correlation outside `[-1, 1]` by at most `1e-12` is clipped to the boundary; a larger violation yields `correlation_out_of_bounds`. A non-finite/non-positive variance yields `correlation_non_positive_variance`; a non-finite correlation yields `correlation_non_finite`.

Correlation PCA fields mirror covariance PCA with `correlation_` prefixes: `correlation_eigenvalues`, `correlation_explained_variance`, `correlation_cumulative_explained_variance`, `correlation_effective_rank`, `correlation_components_for_80pct`, `correlation_components_for_90pct`, `correlation_components_for_95pct`, `correlation_component_coefficients`, `correlation_dominant_component_representative`, and `correlation_dominant_component_share`. Correlation PCA availability is independent of covariance PCA availability after covariance PCA has succeeded.

## 5. Signal-component parallel analysis

Input is the exact aligned daily log-return matrix in canonical listing order. Use exactly `100` null replicates and RNG `numpy.random.Generator(numpy.random.PCG64(41))`. For every replicate independently permute the observation order of each asset column without replacement, preserving each column's values/count while breaking synchronous cross-asset dependence. Re-estimate the production Ledoit-Wolf covariance for each replicate, derive correlation through section 4, and run the same spectral contract.

For eigenvalue rank `k`, `null_threshold_k` is the empirical `0.95` quantile of null eigenvalues at rank `k` using NumPy quantile method `higher`. `signal_component_count` is the number of contiguous leading observed correlation-PCA eigenvalues that are strictly greater than their same-rank thresholds; counting stops at the first non-exceedance.

Persist observed eigenvalues, rank-wise thresholds, `replicate_count=100`, `seed=41`, `quantile=0.95`, `quantile_method="higher"`, and immutable input identity. Failure yields a typed reason; it does not change other structure fields.

## 6. Canonical hierarchical risk clusters

Correlation distance is exactly:

```text
d_ij = sqrt((1 - R_ij) / 2)
```

Canonical clustering uses deterministic agglomerative average linkage. The distance between two clusters is the arithmetic mean of every cross-cluster pair distance. Merge ties resolve by the lexicographically sorted tuple of full listing identities in each candidate cluster pair. Cut the dendrogram at exactly `sqrt((1 - 0.70) / 2)`. A proposed merge whose average-linkage distance is greater than the cut is not performed.

Final clusters are ordered by the lexicographically smallest member identity and labeled `Cluster 1`, `Cluster 2`, … in that order. Output membership rows are ordered by canonical listing order. `largest_redundancy_warning` is the maximum valid pair correlation; ties resolve by ordered full listing identity pair ascending. Invalid correlation yields typed cluster unavailability and no fabricated membership.

## 7. Candidate PCA risk

For candidate weights `w` aligned by full listing identity to covariance PCA component `v_k` with eigenvalue `lambda_k`, component variance contribution is exactly:

```text
c_k = lambda_k * (v_k dot w)^2
```

Tiny negative values in `[-1e-12, 0)` are clipped to zero; lower values yield `candidate_pca_negative_contribution`. The contributions must reconcile with portfolio variance:

```text
sum_k(c_k) == w^T * Sigma * w
```

using `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`. Rows contain `candidate_id`, `method`, `component_id`, `variance_contribution`, `percent_portfolio_variance`, `structure_id`, and `risk_model_id`. Infeasible/unavailable candidates get typed unavailable evidence, never zero rows.

For positive total variance, normalize `q_k = c_k / sum_j(c_j)`. Candidate diagnostics are:

```text
effective_pca_risk_drivers = exp(-sum(q_k * log(q_k) for q_k > 0))
largest_pca_risk_share = max(q_k)
```

`components_for_80pct_risk`, `components_for_90pct_risk`, and `components_for_95pct_risk` are minimal counts after sorting contributions descending, with ties by component ID ascending. Zero/non-finite total variance yields `candidate_pca_non_positive_variance`.

## 8. Candidate cluster-risk attribution

Asset signed variance contribution is `a_i = w_i * (Sigma * w)_i`. For cluster `C`:

```text
signed_cluster_variance_contribution_C = sum(a_i for i in C)
cluster_percent_variance_contribution_C = signed_cluster_variance_contribution_C / portfolio_variance
cluster_gross_abs_risk_share_C = sum(abs(a_i) for i in C) / sum_i(abs(a_i))
```

Signed cluster contributions must sum to portfolio variance with `rel_tol=1e-9`, `abs_tol=1e-12`. Available signed percentages sum to `1.0` under the same tolerance and remain signed; negative values are not clipped. Gross-absolute shares sum to `1.0` when their denominator is positive. Rows are ordered by candidate service order then canonical cluster order and carry exact source identities.

## 9. Rolling structure

Use exactly `252` aligned daily observations per window, stride exactly `21` observations, and at most the `24` most recent windows. The latest window ends on the latest aligned date. Earlier endpoints are exactly 21 aligned observations apart; final output is chronological. Fewer than 252 observations yields `rolling_structure_insufficient_history`.

Every window independently re-estimates production Ledoit-Wolf covariance from only its 252 rows, then recomputes covariance PCA, correlation PCA, and canonical clusters. A row contains window start/end, observation count, covariance/correlation dominant-component shares, covariance/correlation effective ranks, and risk-cluster count. Parallel analysis and cluster bootstrap are not run inside rolling windows.

## 10. PCA leading-subspace stability

For adjacent valid rolling windows, let `k = min(3, listing_count)` and let `U_prev`, `U_curr` contain the first `k` orthonormal component vectors. Compute separately for covariance and correlation PCA:

```text
stability = squared_frobenius_norm(U_prev^T * U_curr) / k
```

Available values are in `[0, 1]` within `1e-12`. The metric is invariant to sign changes and rotations within the same k-dimensional subspace. Fewer than two valid rolling windows yields `subspace_stability_insufficient_windows`.

## 11. Bootstrap cluster stability

Use exactly `100` circular moving-block bootstrap replicates, block length exactly `21`, RNG `numpy.random.Generator(numpy.random.PCG64(41))`. Each replicate concatenates randomly selected circular contiguous blocks and truncates only the final block to reproduce exactly the original aligned observation count. Each replicate re-estimates Ledoit-Wolf, derives correlation and reruns section 6 clustering.

For each canonical listing pair:

```text
co_cluster_probability = same_cluster_replicate_count / 100
```

For each canonical non-singleton cluster persist mean and minimum within-cluster pair co-cluster probability. A singleton cluster reports `cluster_stability_not_applicable_singleton`, never fabricated `1.0`. Persist seed, block length, replicate count, source identities and canonical pair ordering.

## 12. Structural walk-forward evidence

Reuse the production walk-forward split calendar and candidate refit contract. For each completed split, fit Ledoit-Wolf/PCA/clusters on training rows only, compute the refitted candidate's training-period `effective_pca_risk_drivers`, `largest_pca_risk_share`, and largest cluster gross-absolute risk share, then attach the already-defined OOS post-cost return, volatility, CVaR and max drawdown for that exact test window.

Every row records split ID, candidate ID/method, train start/end, test start/end, structural metrics, OOS metrics, and algorithm/source identities. `train_end < test_start` is mandatory. Test-period observations, OOS covariance and future cluster membership MUST NOT influence training-period structural metrics or weights.

## 13. Artifact identity and ordering

`multivariate.structure@v3` identity includes input snapshot ID, risk-model ID, this contract version, all frozen output-affecting parameters, and immutable aligned-input identity. `multivariate.candidate_structure@v2` identity additionally includes exact candidate-set identity. Canonical serialization is deterministic and repeated identical input must be byte-identical. Earlier v2/v1 artifacts remain immutable historical documents.

Universe sub-artifacts preserve section order. Candidate rows preserve deterministic candidate service order, then component/cluster order. Pair rows use lexicographically sorted full identity pairs. Rolling and walk-forward rows are chronological/split-order deterministic.

## 14. Availability reasons

At minimum the implementation recognizes: `risk_model_unavailable`, `spectral_negative_eigenvalue`, `spectral_non_positive_total`, `correlation_non_positive_variance`, `correlation_non_finite`, `correlation_out_of_bounds`, `clusters_unavailable`, `candidate_unavailable`, `candidate_identity_mismatch`, `candidate_pca_negative_contribution`, `candidate_pca_variance_mismatch`, `candidate_pca_non_positive_variance`, `candidate_cluster_variance_mismatch`, `rolling_structure_insufficient_history`, `subspace_stability_insufficient_windows`, `cluster_stability_not_applicable_singleton`, `signal_analysis_unavailable`, and `structural_walk_forward_unavailable`.

Unavailable values are represented by absent/`None` typed fields plus reasons, never `0`, `NaN`, or an implicit fallback.

## 15. Pre-staging/adoption gate

PR361–PR376 may be pre-staged on dependency branches for later adoption, but they remain blocked from production integration until PR360 is merged with final PASS evidence. Pre-staging must not manufacture acceptance evidence or mark a blocked quality gate as passed. PR372 is the first change allowed to switch new production runs to v2 artifacts; PR373/PR374 only render persisted values; PR376 is QA/evidence only and does not authorize a new optimizer objective or candidate.
