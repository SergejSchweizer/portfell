from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from portfell.app_services.research import ApplicationServiceError, ResearchApplicationService
from portfell.app_state.contracts import (
    AnalysisArtifactRecord,
    AnalysisRunRecord,
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
        self.selections: dict[str, UnivariateSelectionRecord] = {}

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
            str(values["universe_id"]), str(values["source_snapshot_id"]), int(values["version"]),
            str(values["content_hash"]), NOW, NOW, tuple(values["members"]),  # type: ignore[arg-type]
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
            run_id, str(values["stage"]), str(values["status"]), str(values["input_snapshot_id"]),
            str(values["input_ref"]), str(values["logical_hash"]), str(values["algorithm_version"]),
            None, NOW, NOW, None,
        )
        self.runs[run_id] = record
        return record

    def transition_analysis_run(
        self, *, run_id: str, status: str, failure_code: str | None = None
    ) -> AnalysisRunRecord:
        old = self.runs[run_id]
        record = AnalysisRunRecord(
            old.run_id, old.stage, status, old.input_snapshot_id, old.input_ref, old.logical_hash,
            old.algorithm_version, failure_code, old.created_at, old.started_at,
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

    def put_analysis_artifact(self, **values: object) -> AnalysisArtifactRecord:
        record = AnalysisArtifactRecord(
            str(values["artifact_id"]), str(values["run_id"]), str(values["artifact_type"]),
            str(values["content_hash"]), dict(values["document"]), NOW,  # type: ignore[arg-type]
        )
        self.artifacts.setdefault(record.run_id, []).append(record)
        return record

    def list_analysis_artifacts(self, run_id: str) -> tuple[AnalysisArtifactRecord, ...]:
        return tuple(self.artifacts.get(run_id, ()))

    def create_univariate_selection(self, **values: object) -> UnivariateSelectionRecord:
        record = UnivariateSelectionRecord(
            str(values["selection_id"]), str(values["source_run_id"]), int(values["version"]),
            str(values["content_hash"]), NOW, NOW, tuple(values["members"]),  # type: ignore[arg-type]
        )
        self.selections[record.selection_id] = record
        return record

    def get_univariate_selection(self, selection_id: str) -> UnivariateSelectionRecord:
        return self.selections[selection_id]

    def list_univariate_selections(
        self, *, limit: int = 100
    ) -> tuple[UnivariateSelectionRecord, ...]:
        return tuple(self.selections.values())[-limit:]


class Gateway:
    def __init__(self) -> None:
        self.keys = (ListingKey("IE00A", "XETRA", "A"), ListingKey("IE00A", "XETRA", "B"))
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
    service = ResearchApplicationService(state, Gateway(), now=lambda: NOW)
    universe = service.create_metadata_universe(exchange="XETRA", instrument_type="ETF")
    assert universe.members == (
        ListingIdentity("IE00A", "XETRA", "A"), ListingIdentity("IE00A", "XETRA", "B"),
    )
    result = service.run_univariate(universe.universe_id)
    assert result["status"] == "succeeded"
    selection = service.create_univariate_selection(str(result["run_id"]))
    assert selection.members == universe.members
    assert service.run_univariate(universe.universe_id)["run_id"] == result["run_id"]


def test_clean_service_fails_closed_when_snapshot_no_longer_has_every_member_quote() -> None:
    state = MemoryState()
    gateway = Gateway()
    service = ResearchApplicationService(state, gateway, now=lambda: NOW)
    universe = service.create_metadata_universe()
    gateway.changed = True
    with pytest.raises(ApplicationServiceError, match="missing_adjusted_close"):
        service.run_univariate(universe.universe_id)
