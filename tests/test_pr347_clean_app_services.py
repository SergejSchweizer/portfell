from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest

from portfell.app_services.analysis_compute import (
    ComputedRun,
    bivariate_source_id,
    filtered_univariate_selection,
    full_univariate_selection,
    univariate_source_id,
)
from portfell.app_services.analysis_executor import AnalysisJobExecutor
from portfell.app_services.workspace import ApplicationServiceError, WorkspaceApplicationService
from portfell.app_state.contracts import (
    AnalysisArtifactItem,
    AnalysisArtifactItemRecord,
    AnalysisArtifactRecord,
    AnalysisJobRecord,
    AnalysisRunRecord,
    DecisionArtifactRecord,
    ListingIdentity,
    MarketSourceSnapshotRecord,
    MetadataUniverseRecord,
    UnivariateSelectionRecord,
)
from portfell.market_source.contracts import EodQuote, Listing, ListingKey
from portfell.market_source.gateway import MarketDataSnapshot

NOW = datetime(2026, 8, 31, tzinfo=UTC)


class MemoryState:
    def __init__(self) -> None:
        self.snapshots: dict[str, MarketSourceSnapshotRecord] = {}
        self.universes: dict[str, MetadataUniverseRecord] = {}
        self.runs: dict[str, AnalysisRunRecord] = {}
        self.artifacts: dict[str, list[AnalysisArtifactRecord]] = {}
        self.artifact_items: dict[str, tuple[AnalysisArtifactItemRecord, ...]] = {}
        self.selections: dict[str, UnivariateSelectionRecord] = {}
        self.decisions: dict[str, DecisionArtifactRecord] = {}
        self.jobs: dict[str, AnalysisJobRecord] = {}
        self.progress_events: list[tuple[int, int | None, str]] = []

    def put_market_source_snapshot(self, **values: object) -> MarketSourceSnapshotRecord:
        identity = str(values["snapshot_id"])
        return self.snapshots.setdefault(
            identity,
            MarketSourceSnapshotRecord(identity, str(values["source_fingerprint"]), NOW, NOW),
        )

    def get_market_source_snapshot(self, snapshot_id: str) -> MarketSourceSnapshotRecord:
        return self.snapshots[snapshot_id]

    def create_metadata_universe(self, **values: object) -> MetadataUniverseRecord:
        record = MetadataUniverseRecord(
            str(values["universe_id"]),
            str(values["source_snapshot_id"]),
            int(values["version"]),
            str(values["content_hash"]),
            NOW,
            NOW,
            tuple(values["members"]),  # type: ignore[arg-type]
        )
        self.universes[record.universe_id] = record
        return record

    def get_metadata_universe(self, universe_id: str) -> MetadataUniverseRecord:
        return self.universes[universe_id]

    def list_metadata_universes(self, *, limit: int = 100) -> tuple[MetadataUniverseRecord, ...]:
        return tuple(self.universes.values())[-limit:]

    def create_analysis_run(self, **values: object) -> AnalysisRunRecord:
        run_id = str(values["run_id"])
        if run_id in self.runs:
            return self.runs[run_id]
        record = AnalysisRunRecord(
            run_id,
            str(values["stage"]),
            str(values["status"]),
            str(values["input_snapshot_id"]),
            str(values["input_ref"]),
            str(values["logical_hash"]),
            str(values["algorithm_version"]),
            None,
            NOW,
            NOW,
            None,
        )
        self.runs[run_id] = record
        return record

    def transition_analysis_run(
        self, *, run_id: str, status: str, failure_code: str | None = None
    ) -> AnalysisRunRecord:
        old = self.runs[run_id]
        record = AnalysisRunRecord(
            old.run_id,
            old.stage,
            status,
            old.input_snapshot_id,
            old.input_ref,
            old.logical_hash,
            old.algorithm_version,
            failure_code,
            old.created_at,
            old.started_at,
            NOW if status in {"succeeded", "failed", "cancelled"} else None,
        )
        self.runs[run_id] = record
        return record

    def get_analysis_run(self, run_id: str) -> AnalysisRunRecord:
        return self.runs[run_id]

    def list_analysis_runs(
        self, *, stage: str | None = None, limit: int = 100
    ) -> tuple[AnalysisRunRecord, ...]:
        rows = tuple(run for run in self.runs.values() if stage is None or run.stage == stage)
        return rows[-limit:]

    def create_or_get_active_job(self, **values: object) -> AnalysisJobRecord:
        existing = next(
            (
                item
                for item in self.jobs.values()
                if item.stage == values["stage"]
                and item.input_ref == values["input_ref"]
                and item.requested_objective == values.get("requested_objective")
                and item.status in {"queued", "running"}
            ),
            None,
        )
        if existing is not None:
            return existing
        objective = values.get("requested_objective")
        record = AnalysisJobRecord(
            str(values["job_id"]),
            str(values["stage"]),
            str(values["input_ref"]),
            objective if isinstance(objective, str) else None,
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
        self.jobs[record.job_id] = record
        return record

    def get_analysis_job(self, job_id: str) -> AnalysisJobRecord:
        return self.jobs[job_id]

    def update_job_progress(
        self, job_id: str, *, current: int, total: int | None, phase: str
    ) -> AnalysisJobRecord:
        current_record = self.jobs[job_id]
        record = replace(
            current_record,
            progress_current=current,
            progress_total=total,
            progress_phase=phase,
        )
        self.jobs[job_id] = record
        self.progress_events.append((current, total, phase))
        return record

    def list_analysis_jobs(
        self, *, stage: str | None = None, status: str | None = None, limit: int = 100
    ) -> tuple[AnalysisJobRecord, ...]:
        return tuple(
            item
            for item in self.jobs.values()
            if (stage is None or item.stage == stage) and (status is None or item.status == status)
        )[-limit:]

    def put_analysis_artifact(self, **values: object) -> AnalysisArtifactRecord:
        record = AnalysisArtifactRecord(
            str(values["artifact_id"]),
            str(values["run_id"]),
            str(values["artifact_type"]),
            str(values["content_hash"]),
            dict(values["document"]),
            NOW,  # type: ignore[arg-type]
        )
        self.artifacts.setdefault(record.run_id, []).append(record)
        return record

    def list_analysis_artifacts(self, run_id: str) -> tuple[AnalysisArtifactRecord, ...]:
        return tuple(self.artifacts.get(run_id, ()))

    def publish_row_backed_analysis_artifact(self, **values: object) -> AnalysisArtifactRecord:
        document = dict(values["document"])
        record = AnalysisArtifactRecord(
            str(values["artifact_id"]),
            str(values["run_id"]),
            str(values["artifact_type"]),
            str(values["content_hash"]),
            document,
            NOW,
        )
        self.artifacts.setdefault(record.run_id, []).append(record)
        items = tuple(cast(tuple[AnalysisArtifactItem, ...], values["items"]))
        self.artifact_items[record.artifact_id] = tuple(
            AnalysisArtifactItemRecord(record.artifact_id, index, item.item_key, item.document)
            for index, item in enumerate(items)
        )
        return record

    def list_analysis_artifact_items(
        self, artifact_id: str, *, offset: int = 0, limit: int = 100
    ) -> tuple[AnalysisArtifactItemRecord, ...]:
        return self.artifact_items[artifact_id][offset : offset + limit]

    def create_univariate_selection(self, **values: object) -> UnivariateSelectionRecord:
        record = UnivariateSelectionRecord(
            str(values["selection_id"]),
            str(values["source_run_id"]),
            int(values["version"]),
            str(values["content_hash"]),
            NOW,
            NOW,
            tuple(values["members"]),  # type: ignore[arg-type]
        )
        self.selections[record.selection_id] = record
        return record

    def get_univariate_selection(self, selection_id: str) -> UnivariateSelectionRecord:
        return self.selections[selection_id]

    def list_univariate_selections(
        self, *, limit: int = 100
    ) -> tuple[UnivariateSelectionRecord, ...]:
        return tuple(self.selections.values())[-limit:]

    def put_decision_artifact(self, **values: object) -> DecisionArtifactRecord:
        record = DecisionArtifactRecord(
            str(values["decision_id"]),
            str(values["run_id"]),
            str(values["objective"]),
            str(values["winning_candidate_id"]),
            str(values["requested_method"]),
            str(values["actual_method"]),
            bool(values["available"]),
            bool(values["production_eligible"]),
            values["reason"] if isinstance(values["reason"], str) else None,
            dict(values["document"]),  # type: ignore[arg-type]
            NOW,
        )
        self.decisions[record.run_id] = record
        return record

    def get_decision_artifact(self, run_id: str) -> DecisionArtifactRecord:
        return self.decisions[run_id]


class Gateway:
    def __init__(self) -> None:
        self.keys = (
            ListingKey("IE00A", "XETRA", "A"),
            ListingKey("IE00B", "XETRA", "C"),
        )
        self.listings = tuple(Listing(key, key.code, "ETF", "IE", "EUR", True) for key in self.keys)
        self.changed = False

    def read_active_listings(self) -> tuple[Listing, ...]:
        return self.listings

    def read_snapshot(
        self, keys: tuple[ListingKey, ...], *, start: date, end: date
    ) -> MarketDataSnapshot:
        assert tuple(sorted(keys)) == self.keys
        quotes = tuple(
            EodQuote(
                key,
                date(2024, 1, 1) + timedelta(days=day),
                None if self.changed and key == keys[-1] and day == 0 else Decimal(100 + day),
                Decimal(100 + day),
                None,
            )
            for key in keys
            for day in range(270)
        )
        return MarketDataSnapshot(self.listings, quotes, (), ())


def test_clean_service_persists_full_identity_metadata_and_univariate_run() -> None:
    state = MemoryState()
    service = WorkspaceApplicationService(state, Gateway(), now=lambda: NOW)
    universe = service.create_metadata_universe(exchange="XETRA", instrument_type="ETF")
    assert universe.members == (
        ListingIdentity("IE00A", "XETRA", "A"),
        ListingIdentity("IE00B", "XETRA", "C"),
    )
    result = service.run_univariate(universe.universe_id)
    assert result["status"] == "succeeded"
    univariate_detail = service.run_detail(str(result["run_id"]))
    daily_manifest = univariate_detail["artifacts"]["univariate.daily_returns@v1"]
    assert daily_manifest["storage"] == "row_items"
    assert daily_manifest["item_count"] == 2 * 269
    selection = service.create_univariate_selection(str(result["run_id"]))
    assert selection.members == universe.members
    assert service.run_univariate(universe.universe_id)["run_id"] == result["run_id"]
    bivariate = service.run_bivariate(selection.selection_id)
    assert bivariate["status"] == "succeeded"
    detail = service.run_detail(str(bivariate["run_id"]))
    assert "bivariate_rows" in detail["artifacts"]
    assert service.stage_history("univariate")[0]["run_id"] == result["run_id"]
    assert service.workflow_state()["stages"]["bivariate"]["status"] == "succeeded"
    multivariate = service.run_multivariate(
        selection_id=selection.selection_id,
        bivariate_run_id=str(bivariate["run_id"]),
    )
    assert multivariate["status"] == "succeeded"
    assert str(multivariate["run_id"]) in state.decisions
    multivariate_detail = service.run_detail(str(multivariate["run_id"]))
    artifacts = multivariate_detail["artifacts"]
    assert isinstance(artifacts, dict)
    for artifact_type in (
        "multivariate.structure@v2",
        "multivariate.candidate_structure@v2",
        "multivariate.structural_walk_forward@v1",
    ):
        assert artifact_type in artifacts
    structure = cast(dict[str, object], artifacts["multivariate.structure@v2"])
    risk_model = cast(dict[str, object], artifacts["risk_model"])
    assert structure["risk_model_id"] == risk_model["risk_model_id"]


def test_workflow_exposes_only_small_persisted_analysis_job_status() -> None:
    state = MemoryState()
    state.jobs["job-a"] = AnalysisJobRecord(
        "job-a",
        "univariate",
        "universe-a",
        None,
        "running",
        None,
        3,
        10,
        "members",
        1,
        NOW,
        None,
        NOW,
        NOW,
        None,
    )
    service = WorkspaceApplicationService(state, Gateway(), now=lambda: NOW)
    assert service.active_analysis_job() is None
    assert service.analysis_job_status("job-a")["progress_current"] == 3
    assert service.workflow_state()["active_job"] is None


def test_clean_service_fails_closed_when_snapshot_no_longer_has_every_member_quote() -> None:
    state = MemoryState()
    gateway = Gateway()
    service = WorkspaceApplicationService(state, gateway, now=lambda: NOW)
    universe = service.create_metadata_universe()
    gateway.changed = True
    with pytest.raises(ApplicationServiceError, match="missing_adjusted_close"):
        service.run_univariate(universe.universe_id)


def test_clean_service_exposes_metadata_filters_and_typed_invalid_requests() -> None:
    service = WorkspaceApplicationService(MemoryState(), Gateway(), now=lambda: NOW)

    assert service.metadata_options()["active_listing_count"] == 2
    assert len(service.active_listings(exchange="xetra", currency="eur")) == 2
    assert service.active_listings(country="DE") == ()
    with pytest.raises(ApplicationServiceError, match="metadata_universe_empty"):
        service.create_metadata_universe(country="DE")

    universe = service.create_metadata_universe()
    univariate = service.run_univariate(universe.universe_id)
    selection = service.create_univariate_selection(str(univariate["run_id"]))
    bivariate = service.run_bivariate(selection.selection_id)
    with pytest.raises(ApplicationServiceError, match="invalid_multivariate_objective"):
        service.run_multivariate(
            selection_id=selection.selection_id,
            bivariate_run_id=str(bivariate["run_id"]),
            objective="not-an-objective",
        )


def test_clean_selection_helpers_preserve_identity_and_reject_invalid_predicates() -> None:
    run = ComputedRun(
        run_id="run-1",
        source_id="source-1",
        algorithm_version="v1",
        rows=(
            {"isin": "IE00A", "exchange": "XETRA", "code": "A", "annual_return_pct": 4.0},
            {"isin": "IE00A", "exchange": "XETRA", "code": "B", "annual_return_pct": 8.0},
        ),
    )
    full = full_univariate_selection(run)
    filtered = filtered_univariate_selection(
        run, ({"metric": "annual_return_pct", "operator": ">=", "value": 6},)
    )
    assert full.member_ids == ("IE00A:XETRA:A", "IE00A:XETRA:B")
    assert filtered.member_ids == ("IE00A:XETRA:B",)
    assert univariate_source_id(universe_id="universe", market_snapshot_id="snapshot")
    assert bivariate_source_id(
        selection_id=filtered.selection_id,
        member_ids=filtered.member_ids,
        market_snapshot_id="snapshot",
    )
    with pytest.raises(ValueError, match="invalid_metric"):
        filtered_univariate_selection(run, ({"metric": "missing", "operator": ">", "value": 1},))
    with pytest.raises(ValueError, match="invalid_predicate_value"):
        filtered_univariate_selection(
            run, ({"metric": "annual_return_pct", "operator": ">", "value": True},)
        )


class RecordingAnalysisExecutor:
    def __init__(self) -> None:
        self.submissions: list[AnalysisJobRecord] = []

    def submit(self, job: AnalysisJobRecord) -> None:
        self.submissions.append(job)

    def recover(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_metadata_kickoff_reuses_one_full_universe_job_and_publishes_v2_rows() -> None:
    state = MemoryState()
    executor = RecordingAnalysisExecutor()
    service = WorkspaceApplicationService(
        state,
        Gateway(),
        analysis_job_executor=cast(AnalysisJobExecutor, executor),
        now=lambda: NOW,
    )

    first = service.create_universe_and_start_univariate(exchange="XETRA", instrument_type="ETF")
    second = service.create_universe_and_start_univariate(exchange="XETRA", instrument_type="ETF")
    assert first["job"] == second["job"]
    assert len(state.universes) == 1
    assert len(state.jobs) == 1
    assert len(executor.submissions) == 2  # executor-side de-duplication owns duplicate submits

    job = next(iter(state.jobs.values()))
    result = service._execute_analysis_job(job)
    assert result["status"] == "succeeded"
    assert state.progress_events[0] == (0, None, "loading_market_data")
    assert state.progress_events[-1] == (2, 2, "members")
    assert all(
        previous[0] <= current[0]
        for previous, current in zip(
            state.progress_events[1:], state.progress_events[2:], strict=False
        )
        if previous[1] is not None and current[1] is not None
    )

    detail = service.run_detail(str(result["run_id"]))
    artifacts = cast(dict[str, object], detail["artifacts"])
    manifest = cast(dict[str, object], artifacts["univariate.rows@v2"])
    assert manifest["storage"] == "row_items"
    assert manifest["item_count"] == 2
    assert "items" not in manifest
    artifact_id = next(
        artifact.artifact_id
        for artifact in state.list_analysis_artifacts(str(result["run_id"]))
        if artifact.artifact_type == "univariate.rows@v2"
    )
    rows = state.list_analysis_artifact_items(artifact_id, limit=500)
    assert [
        (item.document["isin"], item.document["exchange"], item.document["code"]) for item in rows
    ] == [
        ("IE00A", "XETRA", "A"),
        ("IE00B", "XETRA", "C"),
    ]
    assert all("availability_reason" in item.document for item in rows)
    preview = service.univariate_result_preview(str(result["run_id"]), limit=2)
    assert preview["item_count"] == 2
    assert len(cast(list[object], preview["rows"])) == 2
