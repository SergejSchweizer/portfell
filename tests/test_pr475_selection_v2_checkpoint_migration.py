from __future__ import annotations

from types import SimpleNamespace

from portfell.app_services.multivariate_compute import MULTIVARIATE_EXECUTION_VERSION
from portfell.app_services.workspace import WorkspaceApplicationService


class _State:
    def __init__(self):
        self.record = None

    def put_multivariate_checkpoint(self, **kwargs):
        self.record = SimpleNamespace(
            dataset_digest=kwargs["dataset_digest"],
            algorithm_version=kwargs["algorithm_version"],
            phase=kwargs["phase"],
            phase_name=kwargs["phase_name"],
            payload=kwargs["payload"],
        )
        return self.record

    def get_multivariate_checkpoint(self, digest):
        return self.record if self.record and self.record.dataset_digest == digest else None


def _service(state):
    return WorkspaceApplicationService(state, market_gateway=object())


def test_checkpoint_round_trip_is_contract_and_digest_bound() -> None:
    state = _State()
    service = _service(state)
    service._save_multivariate_checkpoint(
        dataset_digest="digest-a",
        phase=5,
        phase_name="structural_diagnostics",
        payload={"phase": 5, "marker": "ranking-and-family"},
    )
    loaded = service._load_multivariate_checkpoint("digest-a")
    assert loaded is not None
    assert loaded["checkpoint_contract"] == "multivariate.checkpoint@v2"
    assert loaded["dataset_digest"] == "digest-a"
    assert loaded["execution_version"] == MULTIVARIATE_EXECUTION_VERSION
    assert loaded["marker"] == "ranking-and-family"
    assert service._load_multivariate_checkpoint("digest-b") is None


def test_old_or_corrupt_checkpoint_is_ignored_safely() -> None:
    state = _State()
    service = _service(state)
    service._save_multivariate_checkpoint(
        dataset_digest="digest-a",
        phase=3,
        phase_name="walk_forward_validation",
        payload={"phase": 3},
    )
    state.record.payload = b"not-a-pickle"
    assert service._load_multivariate_checkpoint("digest-a") is None
    service._save_multivariate_checkpoint(
        dataset_digest="digest-a",
        phase=3,
        phase_name="walk_forward_validation",
        payload={"phase": 2},
    )
    assert service._load_multivariate_checkpoint("digest-a") is None
