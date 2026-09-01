from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any, cast

import pytest

from portfell.app_services.analysis_executor import AnalysisJobExecutor
from portfell.app_services.research import (
    ApplicationMarketGateway,
    ApplicationServiceError,
    AppStatePort,
    ResearchApplicationService,
)
from portfell.app_state.contracts import (
    AnalysisJobRecord,
    AnalysisRunRecord,
    ListingIdentity,
    MetadataUniverseRecord,
    UnivariateSelectionRecord,
)
from portfell.app_state.errors import APP_STATE_CONFLICT, AppStateError

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def job(
    *,
    job_id: str = "job-a",
    status: str = "queued",
    attempt: int = 0,
    stage: str = "univariate",
    input_ref: str = "universe-a",
    requested_objective: str | None = None,
) -> AnalysisJobRecord:
    return AnalysisJobRecord(
        job_id=job_id,
        stage=stage,
        input_ref=input_ref,
        requested_objective=requested_objective,
        status=status,
        run_id=None,
        progress_current=0,
        progress_total=None,
        progress_phase=None,
        attempt=attempt,
        heartbeat_at=None,
        failure_code=None,
        created_at=NOW,
        started_at=None,
        completed_at=None,
    )


class State:
    def __init__(self, records: tuple[AnalysisJobRecord, ...] = ()) -> None:
        self.records = {record.job_id: record for record in records}
        self.claims = 0
        self.links: list[tuple[str, str]] = []
        self.completed: list[tuple[str, str, str | None]] = []

    def claim_job(self, job_id: str, *, stale_before: datetime) -> AnalysisJobRecord:
        self.claims += 1
        record = self.records[job_id]
        if record.status not in {"queued", "running"}:
            raise AppStateError(APP_STATE_CONFLICT)
        return job(job_id=job_id, status="running", attempt=record.attempt + 1)

    def link_job_run(self, job_id: str, run_id: str) -> AnalysisJobRecord:
        self.links.append((job_id, run_id))
        return job(job_id=job_id, status="running", attempt=1)

    def complete_job(
        self, job_id: str, *, status: str, failure_code: str | None = None
    ) -> AnalysisJobRecord:
        self.completed.append((job_id, status, failure_code))
        return job(job_id=job_id, status=status, attempt=1)

    def list_analysis_jobs(
        self, *, stage: str | None = None, status: str | None = None, limit: int = 100
    ) -> tuple[AnalysisJobRecord, ...]:
        return tuple(record for record in self.records.values() if record.status == status)[:limit]


class StartState:
    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str, str | None], AnalysisJobRecord] = {}
        self.submitted: list[AnalysisJobRecord] = []
        self.universe = MetadataUniverseRecord(
            "universe-a", "snapshot-a", 1, "hash-a", NOW, NOW, (ListingIdentity("ISIN", "X", "A"),)
        )
        self.selection = UnivariateSelectionRecord(
            "selection-a",
            "univariate-run",
            1,
            "hash-a",
            NOW,
            NOW,
            (ListingIdentity("ISIN", "X", "A"),),
        )
        self.bivariate = AnalysisRunRecord(
            "bivariate-run",
            "bivariate",
            "succeeded",
            "snapshot-a",
            "selection-a",
            "hash-a",
            "v1",
            None,
            NOW,
            NOW,
            NOW,
        )

    def get_metadata_universe(self, universe_id: str) -> MetadataUniverseRecord:
        assert universe_id == self.universe.universe_id
        return self.universe

    def get_univariate_selection(self, selection_id: str) -> UnivariateSelectionRecord:
        assert selection_id == self.selection.selection_id
        return self.selection

    def get_analysis_run(self, run_id: str) -> AnalysisRunRecord:
        assert run_id == self.bivariate.run_id
        return self.bivariate

    def create_or_get_active_job(self, **values: object) -> AnalysisJobRecord:
        key = (
            str(values["stage"]),
            str(values["input_ref"]),
            cast(str | None, values["requested_objective"]),
        )
        existing = self.jobs.get(key)
        if existing is not None:
            return existing
        record = AnalysisJobRecord(
            str(values["job_id"]),
            key[0],
            key[1],
            key[2],
            "queued",
            None,
            0,
            None,
            None,
            0,
            None,
            None,
            NOW,
            None,
            None,
        )
        self.jobs[key] = record
        return record


class RecordingExecutor:
    def __init__(self, state: StartState) -> None:
        self.state = state
        self.recovered = False
        self.closed = False

    def submit(self, record: AnalysisJobRecord) -> None:
        self.state.submitted.append(record)

    def recover(self) -> None:
        self.recovered = True

    def close(self) -> None:
        self.closed = True


def test_submit_returns_immediately_and_worker_claims_then_persists_success() -> None:
    state = State((job(),))
    completed = Event()

    def runner(_: AnalysisJobRecord) -> dict[str, object]:
        completed.set()
        return {"run_id": "run-a"}

    executor = AnalysisJobExecutor(state, runner, now=lambda: NOW)
    executor.submit(job())
    assert completed.wait(timeout=1)
    executor.close()
    assert state.claims == 1
    assert state.links == [("job-a", "run-a")]
    assert state.completed == [("job-a", "succeeded", None)]


def test_duplicate_submit_converges_and_shutdown_rejects_new_work() -> None:
    state = State((job(),))
    entered = Event()
    release = Event()

    def runner(_: AnalysisJobRecord) -> dict[str, object]:
        entered.set()
        assert release.wait(timeout=1)
        return {"run_id": "run-a"}

    executor = AnalysisJobExecutor(state, runner, now=lambda: NOW)
    executor.submit(job())
    assert entered.wait(timeout=1)
    executor.submit(job())
    assert state.claims == 1
    release.set()
    executor.close()
    executor.submit(job(job_id="job-b"))
    assert state.claims == 1


def test_recovery_scans_only_queued_or_running_and_failure_is_redacted() -> None:
    state = State((job(job_id="queued"), job(job_id="running", status="running")))
    completed = Event()

    def runner(record: AnalysisJobRecord) -> dict[str, object]:
        if record.job_id == "queued":
            raise RuntimeError("postgresql://secret@host/private")
        completed.set()
        return {"run_id": "run-a"}

    executor = AnalysisJobExecutor(
        state,
        runner,
        now=lambda: NOW,
        stale_after=timedelta(seconds=1),
    )
    executor.recover()
    assert completed.wait(timeout=1)
    executor.close()
    assert {item[0] for item in state.completed} == {"queued", "running"}
    failed = next(item for item in state.completed if item[0] == "queued")
    assert failed == ("queued", "failed", "analysis_compute_failed")


def test_start_calls_are_small_idempotent_job_submissions_without_market_reads() -> None:
    state = StartState()
    executor = RecordingExecutor(state)
    service = ResearchApplicationService(
        cast(AppStatePort, state),
        cast(ApplicationMarketGateway, object()),
        analysis_job_executor=cast(AnalysisJobExecutor, executor),
        now=lambda: NOW,
    )
    assert service.start_univariate_job("universe-a")["status"] == "queued"
    assert service.start_univariate_job("universe-a")["job_id"] == state.submitted[0].job_id
    assert service.start_bivariate_job("selection-a")["stage"] == "bivariate"
    assert (
        service.start_multivariate_job(
            selection_id="selection-a", bivariate_run_id="bivariate-run"
        )["requested_objective"]
        == "return_risk"
    )
    assert len(state.submitted) == 4
    with pytest.raises(ApplicationServiceError, match="invalid_multivariate_objective"):
        service.start_multivariate_job(
            selection_id="selection-a", bivariate_run_id="bivariate-run", objective="invalid"
        )
    service.start_background_jobs()
    service.stop_background_jobs()
    assert executor.recovered and executor.closed


def test_worker_dispatches_only_the_requested_stage_and_rejects_unknown_stage() -> None:
    state = StartState()
    service = ResearchApplicationService(
        cast(AppStatePort, state),
        cast(ApplicationMarketGateway, object()),
        analysis_job_executor=cast(AnalysisJobExecutor, RecordingExecutor(state)),
        now=lambda: NOW,
    )

    def run_univariate(universe_id: str) -> dict[str, object]:
        return {"run_id": f"uni-{universe_id}"}

    def run_bivariate(selection_id: str) -> dict[str, object]:
        return {"run_id": f"bi-{selection_id}"}

    def run_multivariate(**values: object) -> dict[str, object]:
        return {"run_id": f"multi-{values['objective']}"}

    implementation = cast(Any, service)
    implementation.run_univariate = run_univariate
    implementation.run_bivariate = run_bivariate
    implementation.run_multivariate = run_multivariate
    assert implementation._execute_analysis_job(job())["run_id"] == "uni-universe-a"
    bivariate_job = job(stage="bivariate", input_ref="selection-a")
    bivariate = implementation._execute_analysis_job(bivariate_job)
    assert bivariate["run_id"] == "bi-selection-a"
    assert (
        implementation._execute_analysis_job(
            job(
                stage="multivariate",
                input_ref="bivariate-run",
                requested_objective="minimum_risk",
            )
        )["run_id"]
        == "multi-minimum_risk"
    )
    with pytest.raises(ApplicationServiceError, match="analysis_job_stage_invalid"):
        implementation._execute_analysis_job(job(stage="unknown"))
