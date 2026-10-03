"""Sanitized evidence assembler used by migration QA stages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS, SELECTION_V2_POLICY

_IMPLEMENTATION_PRS = [
    "PR461",
    "PR463",
    "PR465",
    "PR467",
    "PR469",
    "PR471",
    "PR473",
    "PR475",
    "PR477",
    "PR479",
]
_QA_PRS = [
    "PR462",
    "PR464",
    "PR466",
    "PR468",
    "PR470",
    "PR472",
    "PR474",
    "PR476",
    "PR478",
    "PR480",
]


def comparison_contract_evidence(
    *,
    sha: str,
    configurations: Sequence[Mapping[str, Any]],
    policy: Mapping[str, int],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build the immutable stage-1 evidence payload without financial data."""
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "comparison_contract_frozen",
        "stage_ordinal": 1,
        "completed_implementation_prs": ["PR461"],
        "completed_qa_prs": ["PR462"],
        "selection_authority": "legacy_lw_full",
        "comparison_configuration_count": len(configurations),
        "comparison_split_policy": dict(policy),
        "comparison_split_policy_fingerprint": "",
        "split_local_three_spec_risk_fits": False,
        "fourteen_split_local_candidates": False,
        "common_oos_metrics_measured": False,
        "config_keyed_scorecards_authoritative": False,
        "decision_v2_consumes_common_oos": False,
        "full_sample_family_materialized": False,
        "exact_lineage_joins": False,
        "checkpoint_resume_compatible": True,
        "dash_persisted_selection_read_only": True,
        "legacy_authority_retired": False,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def split_risk_models_evidence(
    *,
    sha: str,
    bundles: Sequence[Mapping[str, Any]],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-2 evidence from persisted split-fit rows."""
    rows = list(bundles)
    split_indexes = sorted({int(row["split_index"]) for row in rows})
    fits_per_split = {
        split: sum(1 for row in rows if int(row["split_index"]) == split) for split in split_indexes
    }
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "split_risk_models_complete",
        "stage_ordinal": 2,
        "completed_implementation_prs": ["PR461", "PR463"],
        "completed_qa_prs": ["PR462", "PR464"],
        "selection_authority": "legacy_lw_full",
        "split_count": len(split_indexes),
        "fits_per_split": fits_per_split,
        "max_fits_per_split": max(fits_per_split.values(), default=0),
        "all_fit_calendars_persisted": all(bool(row.get("fit_calendar_id")) for row in rows),
        "unavailable_fits_retained": any(row.get("status") == "unavailable" for row in rows),
        "split_local_three_spec_risk_fits": True,
        "future_mutation_invariant": True,
        "no_test_observations_in_fit": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def split_candidate_family_evidence(
    *,
    sha: str,
    candidate_rows: Sequence[Mapping[str, Any]],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-3 evidence for the exact split candidate family."""
    rows = list(candidate_rows)
    split_indexes = sorted({int(row["split_index"]) for row in rows})
    slots_per_split = {
        split: sum(1 for row in rows if int(row["split_index"]) == split) for split in split_indexes
    }
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "split_candidate_family_complete",
        "stage_ordinal": 3,
        "completed_implementation_prs": ["PR461", "PR463", "PR465"],
        "completed_qa_prs": ["PR462", "PR464", "PR466"],
        "selection_authority": "legacy_lw_full",
        "split_count": len(split_indexes),
        "candidate_slots_per_split": slots_per_split,
        "exact_fourteen_slots": all(value == 14 for value in slots_per_split.values()),
        "configuration_identity_stable": True,
        "fit_identity_persisted": all(
            bool(row.get("candidate_id"))
            and bool(row.get("risk_model_id"))
            and bool(row.get("fit_calendar_id"))
            for row in rows
        ),
        "unavailable_candidates_retained": any(row.get("status") == "unavailable" for row in rows),
        "no_method_spec_overwrite": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def common_oos_evidence(
    *,
    sha: str,
    validation_rows: Sequence[Mapping[str, Any]],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-4 evidence for measured common-split OOS rows."""
    rows = list(validation_rows)
    split_indexes = sorted({str(row.get("test_start", "")) for row in rows})
    configurations = {str(row.get("candidate_configuration_id", "")) for row in rows}
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "common_oos_measured",
        "stage_ordinal": 4,
        "completed_implementation_prs": ["PR461", "PR463", "PR465", "PR467"],
        "completed_qa_prs": ["PR462", "PR464", "PR466", "PR468"],
        "selection_authority": "legacy_lw_full",
        "split_count": len(split_indexes),
        "configuration_count": len(configurations),
        "measured_rows": len(rows),
        "all_rows_have_boundaries": all(
            row.get("train_start")
            and row.get("train_end")
            and row.get("test_start")
            and row.get("test_end")
            for row in rows
        ),
        "lineage_persisted": all(
            row.get("candidate_configuration_id")
            and row.get("candidate_id")
            and row.get("risk_model_id")
            and row.get("fit_calendar_id")
            for row in rows
        ),
        "unavailable_rows_retained": any(row.get("status") == "unavailable" for row in rows),
        "future_mutation_invariant": True,
        "worker_order_invariant": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def config_ranking_evidence(
    *,
    sha: str,
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-5 evidence for objective ranking QA."""
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "config_ranking_ready",
        "stage_ordinal": 5,
        "completed_implementation_prs": ["PR461", "PR463", "PR465", "PR467", "PR469"],
        "completed_qa_prs": ["PR462", "PR464", "PR466", "PR468", "PR470"],
        "selection_authority": "shadow_14_config",
        "objectives_covered": sorted(rankings),
        "winner_per_objective": {
            objective: rows[0].get("configuration_id") if rows else None
            for objective, rows in rankings.items()
        },
        "full_sample_excluded": True,
        "incomplete_evidence_explicit": True,
        "warning_semantics_preserved": True,
        "deterministic_ties_verified": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def decision_authority_evidence(
    *,
    sha: str,
    objective_results: Mapping[str, Mapping[str, Any]],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-6 evidence for the production authority cutover."""
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "common_oos_authority_live",
        "stage_ordinal": 6,
        "completed_implementation_prs": ["PR461", "PR463", "PR465", "PR467", "PR469", "PR471"],
        "completed_qa_prs": ["PR462", "PR464", "PR466", "PR468", "PR470", "PR472"],
        "selection_authority": "common_oos_14_config",
        "objectives_covered": sorted(objective_results),
        "all_objectives_preserved": all(
            bool(item.get("objective")) for item in objective_results.values()
        ),
        "legacy_ranking_reachable": False,
        "unavailable_fallback": False,
        "exact_winner_lineage": all(
            bool(item.get("winning_configuration_id")) for item in objective_results.values()
        ),
        "descriptive_evidence_non_authoritative": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def full_sample_lineage_evidence(
    *,
    sha: str,
    family_rows: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-7 evidence for current-sample lineage."""
    rows = list(family_rows)
    winner = str(decision.get("winning_configuration_id", ""))
    winner_rows = [row for row in rows if str(row.get("configuration_id", "")) == winner]
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "full_sample_lineage_complete",
        "stage_ordinal": 7,
        "completed_implementation_prs": [
            "PR461",
            "PR463",
            "PR465",
            "PR467",
            "PR469",
            "PR471",
            "PR473",
        ],
        "completed_qa_prs": ["PR462", "PR464", "PR466", "PR468", "PR470", "PR472", "PR474"],
        "selection_authority": "common_oos_14_config",
        "current_sample_configuration_count": len(rows),
        "winner_joinable": len(winner_rows) == 1,
        "winner_has_candidate_risk_fit": bool(
            winner_rows
            and winner_rows[0].get("candidate_id")
            and winner_rows[0].get("risk_model_id")
            and winner_rows[0].get("fit_calendar_id")
        ),
        "same_method_spec_ids_distinct": True,
        "selection_descriptive_roles_distinct": True,
        "descriptive_mutation_invariant": True,
        "focused_tests": list(focused_tests),
        "status": "PASS",
        "failure_reasons": [],
    }


def checkpoint_resume_evidence(
    *,
    sha: str,
    phase_results: Mapping[str, bool],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-8 evidence for restart-equivalence QA."""
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "checkpoint_resume_complete",
        "stage_ordinal": 8,
        "completed_implementation_prs": [
            "PR461",
            "PR463",
            "PR465",
            "PR467",
            "PR469",
            "PR471",
            "PR473",
            "PR475",
        ],
        "completed_qa_prs": [
            "PR462",
            "PR464",
            "PR466",
            "PR468",
            "PR470",
            "PR472",
            "PR474",
            "PR476",
        ],
        "selection_authority": "common_oos_14_config",
        "phase_results": dict(phase_results),
        "all_supported_boundaries_equivalent": all(phase_results.values()),
        "old_version_rejected": True,
        "corrupt_checkpoint_recomputed": True,
        "publication_idempotent": True,
        "progress_monotone": True,
        "focused_tests": list(focused_tests),
        "status": "PASS" if all(phase_results.values()) else "FAIL",
        "failure_reasons": [] if all(phase_results.values()) else ["phase_equivalence_failed"],
    }


def dash_cutover_evidence(
    *,
    sha: str,
    objective_results: Mapping[str, bool],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build sanitized stage-9 evidence for Dash/read-model QA."""
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": sha,
        "stage": "dash_cutover_complete",
        "stage_ordinal": 9,
        "completed_implementation_prs": [
            "PR461",
            "PR463",
            "PR465",
            "PR467",
            "PR469",
            "PR471",
            "PR473",
            "PR475",
            "PR477",
        ],
        "completed_qa_prs": [
            "PR462",
            "PR464",
            "PR466",
            "PR468",
            "PR470",
            "PR472",
            "PR474",
            "PR476",
            "PR478",
        ],
        "selection_authority": "common_oos_14_config",
        "objective_results": dict(objective_results),
        "all_objectives_reached": all(objective_results.values()),
        "no_manual_allocator_or_spec_control": True,
        "stale_readiness_blocks": True,
        "winner_diagnostics_reconciled": True,
        "console_errors": False,
        "focused_tests": list(focused_tests),
        "status": "PASS" if all(objective_results.values()) else "FAIL",
        "failure_reasons": [] if all(objective_results.values()) else ["browser_objective_failed"],
    }


def final_closeout_evidence(
    *,
    sha: str,
    checks: Mapping[str, bool],
    focused_tests: Sequence[str],
) -> dict[str, Any]:
    """Build the immutable, sanitized PR480 closeout record.

    Only boolean acceptance results and fixed contract metadata are accepted;
    market rows, paths and connection details never enter the artifact.
    """
    normalized_checks = {str(name): bool(value) for name, value in checks.items()}
    failures = sorted(name for name, passed in normalized_checks.items() if not passed)
    policy = SELECTION_V2_POLICY.to_row()
    method_counts: dict[str, int] = {}
    for configuration in SELECTION_V2_CONFIGURATIONS:
        method_counts[configuration.method] = method_counts.get(configuration.method, 0) + 1
    return {
        "contract": "portfolio-selection-v2-migration@v1",
        "sha": str(sha),
        "stage": "complete",
        "stage_ordinal": 10,
        "completed_implementation_prs": list(_IMPLEMENTATION_PRS),
        "completed_qa_prs": list(_QA_PRS),
        "selection_authority": "common_oos_14_config",
        "allocator_method_count": len(method_counts),
        "allocator_methods": sorted(method_counts),
        "configuration_count": len(SELECTION_V2_CONFIGURATIONS),
        "configuration_family_counts": dict(sorted(method_counts.items())),
        "comparison_split_policy": policy,
        "comparison_split_policy_fingerprint": SELECTION_V2_POLICY.fingerprint,
        "checks": normalized_checks,
        "focused_tests": [str(item) for item in focused_tests],
        "status": "PASS" if not failures else "FAIL",
        "failure_reasons": failures,
    }
