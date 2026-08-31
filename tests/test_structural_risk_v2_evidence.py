import pytest

from portfell.structural_risk_v2_qa import (
    REQUIRED_EVIDENCE_CHECKS,
    build_structural_risk_v2_pass_evidence,
    pending_structural_risk_v2_checks,
)


def _checks() -> dict[str, dict[str, object]]:
    return {
        name: {
            "status": "PASS",
            "executed": True,
            "evidence": f"fixture://{name}",
        }
        for name in REQUIRED_EVIDENCE_CHECKS
    }


def _build(
    *,
    checks: dict[str, dict[str, object]] | None = None,
    commit_sha: str = "a" * 40,
    contract_versions: dict[str, str] | None = None,
) -> dict[str, object]:
    return build_structural_risk_v2_pass_evidence(
        commit_sha=commit_sha,
        contract_versions=contract_versions
        or {
            "candidate": "multivariate.candidates@v7",
            "risk_model": "multivariate.risk_model@v1",
            "structure": "multivariate.structure@v3",
            "candidate_structure": "multivariate.candidate_structure@v2",
            "walk_forward": "multivariate.structural_walk_forward@v1",
        },
        algorithm_versions={"risk_model": 1, "structure_v2": 2},
        test_counts={"unit": 1200, "integration": 200, "browser": 12},
        fixture_fingerprints={
            "independent_numerical": "sha256:fixture-a",
            "walk_forward": "sha256:fixture-b",
        },
        checks=checks or _checks(),
    )


def test_pass_evidence_is_deterministic_and_contains_frozen_contract() -> None:
    first = _build()
    second = _build()
    assert first == second
    assert first["status"] == "PASS"
    assert first["contract_version"] == "structural-risk-v2@v1"
    assert first["git_sha"] == "a" * 40
    frozen = first["frozen_parameters"]
    assert isinstance(frozen, dict)
    assert frozen["parallel_analysis"] == {
        "replicates": 100,
        "rng": "numpy.random.Generator(numpy.random.PCG64(41))",
        "seed": 41,
        "quantile": 0.95,
        "quantile_method": "higher",
    }
    assert frozen["rolling"] == {
        "observations": 252,
        "stride": 21,
        "max_windows": 24,
        "anchor": "latest-date",
    }


def test_missing_or_unexecuted_check_cannot_be_assembled_as_pass() -> None:
    checks = _checks()
    checks["merge_gate"] = {"status": "PASS", "executed": False, "evidence": ""}
    assert pending_structural_risk_v2_checks(checks) == ("merge_gate",)
    with pytest.raises(ValueError, match="checks_incomplete:merge_gate"):
        _build(checks=checks)


def test_exact_40_hex_commit_sha_is_required() -> None:
    with pytest.raises(ValueError, match="exact_git_sha_required"):
        _build(commit_sha="main")


def test_sensitive_fields_are_rejected_from_sanitized_evidence() -> None:
    with pytest.raises(ValueError, match="sensitive_field"):
        _build(
            contract_versions={
                "structure": "multivariate.structure@v3",
                "database_password": "forbidden",
            }
        )
