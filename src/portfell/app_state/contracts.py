"""Typed records and repository ports for the clean application-state database."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, order=True)
class ListingIdentity:
    isin: str
    exchange: str
    code: str


@dataclass(frozen=True)
class MarketSourceSnapshotRecord:
    snapshot_id: str
    source_fingerprint: str
    observed_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class MetadataUniverseRecord:
    universe_id: str
    source_snapshot_id: str
    version: int
    content_hash: str
    created_at: datetime
    published_at: datetime
    members: tuple[ListingIdentity, ...]


@dataclass(frozen=True)
class AnalysisRunRecord:
    run_id: str
    stage: str
    status: str
    input_snapshot_id: str
    input_ref: str
    logical_hash: str
    algorithm_version: str
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class AnalysisArtifactRecord:
    artifact_id: str
    run_id: str
    artifact_type: str
    content_hash: str
    document: JsonObject
    created_at: datetime


@dataclass(frozen=True)
class UnivariateSelectionRecord:
    selection_id: str
    source_run_id: str
    version: int
    content_hash: str
    created_at: datetime
    published_at: datetime
    members: tuple[ListingIdentity, ...]


@dataclass(frozen=True)
class DecisionArtifactRecord:
    decision_id: str
    run_id: str
    objective: str
    winning_candidate_id: str
    requested_method: str
    actual_method: str
    available: bool
    production_eligible: bool
    reason: str | None
    document: JsonObject
    created_at: datetime


@dataclass(frozen=True)
class UiPreferenceRecord:
    key: str
    value: JsonValue
    updated_at: datetime


class MarketSourceSnapshotRepository(Protocol):
    def put_market_source_snapshot(
        self, *, snapshot_id: str, source_fingerprint: str, observed_at: datetime
    ) -> MarketSourceSnapshotRecord: ...

    def get_market_source_snapshot(self, snapshot_id: str) -> MarketSourceSnapshotRecord: ...


class MetadataUniverseRepository(Protocol):
    def create_metadata_universe(
        self,
        *,
        universe_id: str,
        source_snapshot_id: str,
        version: int,
        content_hash: str,
        members: Sequence[ListingIdentity],
    ) -> MetadataUniverseRecord: ...

    def get_metadata_universe(self, universe_id: str) -> MetadataUniverseRecord: ...

    def list_metadata_universes(
        self, *, limit: int = 100
    ) -> tuple[MetadataUniverseRecord, ...]: ...


class AnalysisRunRepository(Protocol):
    def create_analysis_run(
        self,
        *,
        run_id: str,
        stage: str,
        status: str,
        input_snapshot_id: str,
        input_ref: str,
        logical_hash: str,
        algorithm_version: str,
    ) -> AnalysisRunRecord: ...

    def transition_analysis_run(
        self, *, run_id: str, status: str, failure_code: str | None = None
    ) -> AnalysisRunRecord: ...

    def get_analysis_run(self, run_id: str) -> AnalysisRunRecord: ...

    def list_analysis_runs(
        self, *, stage: str | None = None, limit: int = 100
    ) -> tuple[AnalysisRunRecord, ...]: ...


class AnalysisArtifactRepository(Protocol):
    def put_analysis_artifact(
        self,
        *,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        content_hash: str,
        document: Mapping[str, JsonValue],
    ) -> AnalysisArtifactRecord: ...

    def list_analysis_artifacts(self, run_id: str) -> tuple[AnalysisArtifactRecord, ...]: ...


class UnivariateSelectionRepository(Protocol):
    def create_univariate_selection(
        self,
        *,
        selection_id: str,
        source_run_id: str,
        version: int,
        content_hash: str,
        members: Sequence[ListingIdentity],
    ) -> UnivariateSelectionRecord: ...

    def get_univariate_selection(self, selection_id: str) -> UnivariateSelectionRecord: ...

    def list_univariate_selections(
        self, *, limit: int = 100
    ) -> tuple[UnivariateSelectionRecord, ...]: ...


class DecisionArtifactRepository(Protocol):
    def put_decision_artifact(
        self,
        *,
        decision_id: str,
        run_id: str,
        objective: str,
        winning_candidate_id: str,
        requested_method: str,
        actual_method: str,
        available: bool,
        production_eligible: bool,
        reason: str | None,
        document: Mapping[str, JsonValue],
    ) -> DecisionArtifactRecord: ...

    def get_decision_artifact(self, run_id: str) -> DecisionArtifactRecord: ...


class UiPreferenceRepository(Protocol):
    def set_ui_preference(self, key: str, value: JsonValue) -> UiPreferenceRecord: ...

    def get_ui_preference(self, key: str) -> UiPreferenceRecord | None: ...

    def list_ui_preferences(self) -> tuple[UiPreferenceRecord, ...]: ...
