from __future__ import annotations

from migration_evidence import checkpoint_resume_evidence
from test_pr475_selection_v2_checkpoint_migration import _service, _State


def test_every_supported_phase_round_trips_equivalently() -> None:
    state = _State()
    service = _service(state)
    phases = {
        2: "risk_model_and_candidates",
        3: "walk_forward_validation",
        5: "structural_diagnostics",
        6: "decision",
    }
    results = {}
    for phase, name in phases.items():
        payload = {"phase": phase, "selection": {"phase": phase, "value": "stable"}}
        service._save_multivariate_checkpoint(
            dataset_digest="digest", phase=phase, phase_name=name, payload=payload
        )
        loaded = service._load_multivariate_checkpoint("digest")
        results[name] = loaded is not None and loaded["selection"] == payload["selection"]
    assert all(results.values())
    evidence = checkpoint_resume_evidence(
        sha="test-sha",
        phase_results=results,
        focused_tests=["test_pr476_selection_v2_checkpoint_qa.py"],
    )
    assert evidence["all_supported_boundaries_equivalent"]
    assert evidence["status"] == "PASS"


def test_version_mismatch_and_corruption_never_reuse_semantic_state() -> None:
    state = _State()
    service = _service(state)
    service._save_multivariate_checkpoint(
        dataset_digest="digest",
        phase=6,
        phase_name="decision",
        payload={"phase": 6, "value": "old"},
    )
    state.record.algorithm_version = "multivariate_execution.old"
    assert service._load_multivariate_checkpoint("digest") is None
    service._save_multivariate_checkpoint(
        dataset_digest="digest",
        phase=6,
        phase_name="decision",
        payload={"phase": 6, "value": "current"},
    )
    state.record.payload = b"corrupt"
    assert service._load_multivariate_checkpoint("digest") is None


def test_repeated_same_checkpoint_publication_is_idempotent() -> None:
    state = _State()
    service = _service(state)
    payload = {"phase": 5, "value": "same"}
    service._save_multivariate_checkpoint(
        dataset_digest="digest", phase=5, phase_name="structural_diagnostics", payload=payload
    )
    first = state.record.payload
    service._save_multivariate_checkpoint(
        dataset_digest="digest", phase=5, phase_name="structural_diagnostics", payload=payload
    )
    assert state.record.payload == first
