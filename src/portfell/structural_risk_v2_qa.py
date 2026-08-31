"""QA-only evidence contract for the Structural Risk v2 integration gate.

This module does not execute quality/browser jobs and cannot manufacture PASS
evidence. It only validates and deterministically assembles evidence references
that were produced by actually executed checks for one exact commit.
"""

from __future__ import annotations

from collections.abc import Mapping
from re import fullmatch
from typing import Any, cast

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.table_io import JsonRow

STRUCTURAL_RISK_V2_EVIDENCE_CONTRACT = ContractVersion("structural-risk-v2", 1)

REQUIRED_EVIDENCE_CHECKS = (
    "independent_numerical_fixtures",
    "parallel_analysis_contract",
    "cluster_bootstrap_contract",
    "rolling_window_contract",
    "walk_forward_regression",
    "production_multivariate_artifacts",
    "subspace_stability_rows",
    "candidate_cluster_max",
    "structural_walk_forward_identity",
    "persistence_restart",
    "restart_byte_equivalence",
    "read_path_no_recompute",
    "dash_browser_1440x900",
    "dash_browser_1024x768",
    "dash_browser_390x844",
    "negative_space_scan",
    "runtime_docs_reconciled",
    "numpy_dependency_locked",
    "pr_gate",
    "merge_gate",
)

FROZEN_STRUCTURAL_RISK_V2_PARAMETERS: JsonRow = {
    "explained_variance_thresholds": [0.80, 0.90, 0.95],
    "cluster_correlation_cut": 0.70,
    "cluster_distance_cut_formula": "sqrt((1-0.70)/2)",
    "parallel_analysis": {
        "replicates": 100,
        "rng": "numpy.random.Generator(numpy.random.PCG64(41))",
        "seed": 41,
        "quantile": 0.95,
        "quantile_method": "higher",
    },
    "rolling": {
        "observations": 252,
        "stride": 21,
        "max_windows": 24,
        "anchor": "latest-date",
    },
    "subspace_components": "min(3,N)",
    "cluster_bootstrap": {
        "replicates": 100,
        "block_length": 21,
        "seed": 41,
        "circular": True,
    },
}

_SENSITIVE_KEY_FRAGMENTS = (
    "credential",
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "dsn",
)


def pending_structural_risk_v2_checks(
    checks: Mapping[str, Mapping[str, object]],
) -> tuple[str, ...]:
    """Return required checks that have not supplied executed PASS evidence."""

    pending: list[str] = []
    for name in REQUIRED_EVIDENCE_CHECKS:
        row = checks.get(name, {})
        if (
            row.get("status") != "PASS"
            or row.get("executed") is not True
            or not row.get("evidence")
        ):
            pending.append(name)
    return tuple(pending)


def build_structural_risk_v2_pass_evidence(
    *,
    commit_sha: str,
    contract_versions: Mapping[str, str],
    algorithm_versions: Mapping[str, int | str],
    test_counts: Mapping[str, int],
    fixture_fingerprints: Mapping[str, str],
    checks: Mapping[str, Mapping[str, object]],
) -> JsonRow:
    """Assemble deterministic sanitized PASS evidence from executed check references.

    The caller is responsible for collecting check references from the exact
    commit being certified. Missing, skipped, failed, synthetic, or unreferenced
    checks are rejected rather than downgraded to a fabricated PASS.
    """

    if fullmatch(r"[0-9a-f]{40}", commit_sha) is None:
        raise ValueError("structural_risk_v2_exact_git_sha_required")
    pending = pending_structural_risk_v2_checks(checks)
    if pending:
        raise ValueError("structural_risk_v2_checks_incomplete:" + ",".join(pending))
    if not contract_versions or any(
        not key or not value for key, value in contract_versions.items()
    ):
        raise ValueError("structural_risk_v2_contract_versions_required")
    if not algorithm_versions or any(not key for key in algorithm_versions):
        raise ValueError("structural_risk_v2_algorithm_versions_required")
    if not test_counts or any(not key or value < 0 for key, value in test_counts.items()):
        raise ValueError("structural_risk_v2_test_counts_required")
    if not fixture_fingerprints or any(
        not key or not value for key, value in fixture_fingerprints.items()
    ):
        raise ValueError("structural_risk_v2_fixture_fingerprints_required")

    normalized_checks = {
        name: {
            "status": "PASS",
            "executed": True,
            "evidence": str(checks[name]["evidence"]),
        }
        for name in REQUIRED_EVIDENCE_CHECKS
    }
    payload: JsonRow = {
        "contract_version": STRUCTURAL_RISK_V2_EVIDENCE_CONTRACT.qualified_name,
        "status": "PASS",
        "git_sha": commit_sha,
        "contract_versions": dict(sorted(contract_versions.items())),
        "algorithm_versions": dict(sorted(algorithm_versions.items())),
        "frozen_parameters": FROZEN_STRUCTURAL_RISK_V2_PARAMETERS,
        "test_counts": dict(sorted(test_counts.items())),
        "fixture_fingerprints": dict(sorted(fixture_fingerprints.items())),
        "checks": normalized_checks,
    }
    _reject_sensitive_material(payload)
    evidence_id = stable_contract_id("structural_risk_v2_pass_evidence", payload)
    return {"evidence_id": evidence_id, **payload}


def _reject_sensitive_material(value: object, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, Any], value)
        for key, child in mapping.items():
            key_text = key.lower()
            if any(fragment in key_text for fragment in _SENSITIVE_KEY_FRAGMENTS):
                raise ValueError(f"structural_risk_v2_sensitive_field:{path}.{key}")
            _reject_sensitive_material(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        children = cast(list[object] | tuple[object, ...], value)
        for index, child in enumerate(children):
            _reject_sensitive_material(child, path=f"{path}[{index}]")


__all__ = [
    "FROZEN_STRUCTURAL_RISK_V2_PARAMETERS",
    "REQUIRED_EVIDENCE_CHECKS",
    "STRUCTURAL_RISK_V2_EVIDENCE_CONTRACT",
    "build_structural_risk_v2_pass_evidence",
    "pending_structural_risk_v2_checks",
]
