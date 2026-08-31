from pathlib import Path

from portfell.structural_risk_v2_qa import REQUIRED_EVIDENCE_CHECKS

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_multivariate_path_publishes_all_structural_artifacts() -> None:
    source = _source("src/portfell/app_services/multivariate_compute.py")
    for required in (
        "build_structure_v2_documents(",
        "build_structural_walk_forward_evidence(",
        '"multivariate.structure@v2"',
        '"multivariate.candidate_structure@v2"',
        '"multivariate.structural_walk_forward@v1"',
    ):
        assert required in source
    assert "refitted_candidate_sets=refitted" in source
    assert "validation_splits=validation" in source


def test_structure_assembler_contains_real_subspace_and_candidate_cluster_max() -> None:
    source = _source("src/portfell/multivariate_structure_artifacts.py")
    assert "build_adjacent_subspace_stability(" in source
    assert '"subspace_stability"' in source
    assert "subspace_stability_adapter_pending" not in source
    assert '"largest_cluster_gross_abs_risk_share"' in source
    assert "max(row.gross_abs_risk_share for row in cluster_risk.rows)" in source


def test_persisted_read_path_does_not_recompute_structure_v2() -> None:
    service = _source("src/portfell/app_services/research.py")
    run_detail = service.split("    def run_detail(", 1)[1].split("    def stage_history(", 1)[0]
    for forbidden in (
        "build_structure_v2_documents",
        "build_structural_walk_forward_evidence",
        "build_multivariate_risk_model",
        "compute_multivariate(",
    ):
        assert forbidden not in run_detail
    assert "list_analysis_artifacts" in run_detail
    assert "get_decision_artifact" in run_detail


def test_v2_structural_diagnostics_remain_outside_decision_ranking() -> None:
    source = _source("src/portfell/app_services/multivariate_compute.py")
    select_decision = source.split("def _select_decision(", 1)[1].split("def _objective_score(", 1)[
        0
    ]
    for forbidden in (
        "structure_v2",
        "structural_walk_forward",
        "effective_pca_risk_drivers",
        "largest_pca_risk_share",
        "largest_cluster_gross_abs_risk_share",
        "risk_clusters",
    ):
        assert forbidden not in select_decision


def test_pr381_evidence_contract_requires_production_closeout_proof() -> None:
    required = set(REQUIRED_EVIDENCE_CHECKS)
    assert {
        "production_multivariate_artifacts",
        "subspace_stability_rows",
        "candidate_cluster_max",
        "structural_walk_forward_identity",
        "persistence_restart",
        "restart_byte_equivalence",
        "read_path_no_recompute",
        "runtime_docs_reconciled",
        "merge_gate",
    } <= required


def test_runtime_documentation_uses_current_two_database_dash_topology() -> None:
    readme = _source("README.md")
    architecture = _source("ARCHITECTURE.md")
    combined = readme + "\n" + architecture
    assert "portfell_dash" in combined
    assert "xetra_loader" in combined
    assert "Plotly Dash" in combined or "Dash" in combined
    assert "no first-party React/Vite/TypeScript/TanStack application" in readme


def test_retired_v2_labels_are_not_used_by_live_dash_presenters() -> None:
    live_sources = "\n".join(
        _source(path)
        for path in (
            "src/portfell/dash_app/pages/multivariate.py",
            "src/portfell/dash_app/structure_presenters.py",
            "src/portfell/dash_app/candidate_structure_presenters.py",
        )
    )
    assert "effective_independent_drivers" not in live_sources
    assert "strongest_common_driver" not in live_sources
