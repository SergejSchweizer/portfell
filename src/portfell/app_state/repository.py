"""Parameterized PostgreSQL repositories for the clean single-workspace app state."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol, cast

from portfell.app_state.contracts import (
    AnalysisArtifactRecord,
    AnalysisRunRecord,
    DecisionArtifactRecord,
    JsonObject,
    JsonValue,
    ListingIdentity,
    MarketSourceSnapshotRecord,
    MetadataUniverseRecord,
    UiPreferenceRecord,
    UnivariateSelectionRecord,
)
from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_INVALID_TRANSITION,
    APP_STATE_NOT_FOUND,
    APP_STATE_PERSISTENCE_FAILED,
    AppStateError,
)
from portfell.app_state.schema import ANALYSIS_STAGES, ANALYSIS_STATUSES, MULTIVARIATE_OBJECTIVES


class RepositoryCursor(Protocol):
    def fetchone(self) -> Sequence[object] | None: ...

    def fetchall(self) -> list[Sequence[object]]: ...


class RepositoryConnection(Protocol):
    def execute(self, query: str, params: Sequence[object] | None = None) -> RepositoryCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class PostgresAppStateRepository:
    """One transaction boundary implementing every v1 application-state repository port."""

    def __init__(self, connection: RepositoryConnection) -> None:
        self._connection = connection

    def put_market_source_snapshot(
        self, *, snapshot_id: str, source_fingerprint: str, observed_at: datetime
    ) -> MarketSourceSnapshotRecord:
        existing = self._connection.execute(
            """select snapshot_id, source_fingerprint, observed_at, created_at
               from portfell.market_source_snapshots where source_fingerprint = %s""",
            (source_fingerprint,),
        ).fetchone()
        if existing is not None:
            return _snapshot(existing)
        try:
            self._connection.execute(
                """insert into portfell.market_source_snapshots
                   (snapshot_id, source_fingerprint, observed_at)
                   values (%s, %s, %s)""",
                (snapshot_id, source_fingerprint, observed_at),
            )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self.get_market_source_snapshot(snapshot_id)

    def get_market_source_snapshot(self, snapshot_id: str) -> MarketSourceSnapshotRecord:
        row = self._connection.execute(
            """select snapshot_id, source_fingerprint, observed_at, created_at
               from portfell.market_source_snapshots where snapshot_id = %s""",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _snapshot(row)

    def create_metadata_universe(
        self,
        *,
        universe_id: str,
        source_snapshot_id: str,
        version: int,
        content_hash: str,
        members: Sequence[ListingIdentity],
    ) -> MetadataUniverseRecord:
        existing = self._connection.execute(
            """select universe_id from portfell.metadata_universes
               where workspace_id = 'default' and content_hash = %s""",
            (content_hash,),
        ).fetchone()
        if existing is not None:
            return self.get_metadata_universe(str(existing[0]))
        ordered = _canonical_members(members)
        try:
            self._connection.execute(
                """insert into portfell.metadata_universes
                   (universe_id, workspace_id, source_snapshot_id, version, content_hash)
                   values (%s, 'default', %s, %s, %s)""",
                (universe_id, source_snapshot_id, version, content_hash),
            )
            for ordinal, member in enumerate(ordered):
                self._connection.execute(
                    """insert into portfell.metadata_universe_members
                       (universe_id, isin, exchange, code, ordinal)
                       values (%s, %s, %s, %s, %s)""",
                    (universe_id, member.isin, member.exchange, member.code, ordinal),
                )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self.get_metadata_universe(universe_id)

    def get_metadata_universe(self, universe_id: str) -> MetadataUniverseRecord:
        row = self._connection.execute(
            """select universe_id, source_snapshot_id, version, content_hash,
                      created_at, published_at
               from portfell.metadata_universes
               where workspace_id = 'default' and universe_id = %s""",
            (universe_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _universe(row, self._universe_members(universe_id))

    def list_metadata_universes(self, *, limit: int = 100) -> tuple[MetadataUniverseRecord, ...]:
        rows = self._connection.execute(
            """select universe_id, source_snapshot_id, version, content_hash,
                      created_at, published_at
               from portfell.metadata_universes where workspace_id = 'default'
               order by version desc, universe_id limit %s""",
            (_bounded_limit(limit),),
        ).fetchall()
        return tuple(_universe(row, self._universe_members(str(row[0]))) for row in rows)

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
    ) -> AnalysisRunRecord:
        if stage not in ANALYSIS_STAGES or status not in {"queued", "running"}:
            raise AppStateError(APP_STATE_INVALID_TRANSITION)
        existing = self._connection.execute(
            """select run_id from portfell.analysis_runs
               where workspace_id = 'default' and stage = %s and logical_hash = %s""",
            (stage, logical_hash),
        ).fetchone()
        if existing is not None:
            return self.get_analysis_run(str(existing[0]))
        try:
            self._connection.execute(
                """insert into portfell.analysis_runs
                   (run_id, workspace_id, stage, status, input_snapshot_id, input_ref,
                    logical_hash, algorithm_version, started_at)
                   values (%s, 'default', %s, %s, %s, %s, %s, %s,
                           case when %s = 'running' then now() else null end)""",
                (
                    run_id,
                    stage,
                    status,
                    input_snapshot_id,
                    input_ref,
                    logical_hash,
                    algorithm_version,
                    status,
                ),
            )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self.get_analysis_run(run_id)

    def transition_analysis_run(
        self, *, run_id: str, status: str, failure_code: str | None = None
    ) -> AnalysisRunRecord:
        if status not in ANALYSIS_STATUSES or status == "queued":
            raise AppStateError(APP_STATE_INVALID_TRANSITION)
        if (status == "failed") != (failure_code is not None):
            raise AppStateError(APP_STATE_INVALID_TRANSITION)
        try:
            if status == "running":
                self._connection.execute(
                    """update portfell.analysis_runs
                       set status = %s, started_at = coalesce(started_at, now()),
                           completed_at = null, failure_code = null
                       where workspace_id = 'default' and run_id = %s""",
                    (status, run_id),
                )
            else:
                self._connection.execute(
                    """update portfell.analysis_runs
                       set status = %s, completed_at = now(), failure_code = %s
                       where workspace_id = 'default' and run_id = %s""",
                    (status, failure_code, run_id),
                )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_INVALID_TRANSITION) from error
        return self.get_analysis_run(run_id)

    def get_analysis_run(self, run_id: str) -> AnalysisRunRecord:
        row = self._connection.execute(
            """select run_id, stage, status, input_snapshot_id, input_ref, logical_hash,
                      algorithm_version, failure_code, created_at, started_at, completed_at
               from portfell.analysis_runs
               where workspace_id = 'default' and run_id = %s""",
            (run_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _run(row)

    def list_analysis_runs(
        self, *, stage: str | None = None, limit: int = 100
    ) -> tuple[AnalysisRunRecord, ...]:
        bounded = _bounded_limit(limit)
        if stage is None:
            rows = self._connection.execute(
                """select run_id, stage, status, input_snapshot_id, input_ref, logical_hash,
                          algorithm_version, failure_code, created_at, started_at, completed_at
                   from portfell.analysis_runs where workspace_id = 'default'
                   order by created_at desc, run_id limit %s""",
                (bounded,),
            ).fetchall()
        else:
            if stage not in ANALYSIS_STAGES:
                raise AppStateError(APP_STATE_NOT_FOUND)
            rows = self._connection.execute(
                """select run_id, stage, status, input_snapshot_id, input_ref, logical_hash,
                          algorithm_version, failure_code, created_at, started_at, completed_at
                   from portfell.analysis_runs
                   where workspace_id = 'default' and stage = %s
                   order by created_at desc, run_id limit %s""",
                (stage, bounded),
            ).fetchall()
        return tuple(_run(row) for row in rows)

    def put_analysis_artifact(
        self,
        *,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        content_hash: str,
        document: Mapping[str, JsonValue],
    ) -> AnalysisArtifactRecord:
        existing = self._connection.execute(
            """select artifact_id, run_id, artifact_type, content_hash, document, created_at
               from portfell.analysis_artifacts where run_id = %s and artifact_type = %s""",
            (run_id, artifact_type),
        ).fetchone()
        if existing is not None:
            record = _artifact(existing)
            if record.content_hash != content_hash:
                raise AppStateError(APP_STATE_CONFLICT)
            return record
        try:
            self._connection.execute(
                """insert into portfell.analysis_artifacts
                   (artifact_id, run_id, artifact_type, content_hash, document)
                   values (%s, %s, %s, %s, %s::jsonb)""",
                (artifact_id, run_id, artifact_type, content_hash, _json_dump(document)),
            )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self._analysis_artifact(artifact_id)

    def list_analysis_artifacts(self, run_id: str) -> tuple[AnalysisArtifactRecord, ...]:
        rows = self._connection.execute(
            """select artifact_id, run_id, artifact_type, content_hash, document, created_at
               from portfell.analysis_artifacts where run_id = %s
               order by artifact_type, artifact_id""",
            (run_id,),
        ).fetchall()
        return tuple(_artifact(row) for row in rows)

    def create_univariate_selection(
        self,
        *,
        selection_id: str,
        source_run_id: str,
        version: int,
        content_hash: str,
        members: Sequence[ListingIdentity],
    ) -> UnivariateSelectionRecord:
        existing = self._connection.execute(
            """select selection_id from portfell.univariate_selections
               where workspace_id = 'default' and content_hash = %s""",
            (content_hash,),
        ).fetchone()
        if existing is not None:
            return self.get_univariate_selection(str(existing[0]))
        ordered = _canonical_members(members)
        try:
            self._connection.execute(
                """insert into portfell.univariate_selections
                   (selection_id, workspace_id, source_run_id, version, content_hash)
                   values (%s, 'default', %s, %s, %s)""",
                (selection_id, source_run_id, version, content_hash),
            )
            for ordinal, member in enumerate(ordered):
                self._connection.execute(
                    """insert into portfell.univariate_selection_members
                       (selection_id, isin, exchange, code, ordinal)
                       values (%s, %s, %s, %s, %s)""",
                    (selection_id, member.isin, member.exchange, member.code, ordinal),
                )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self.get_univariate_selection(selection_id)

    def get_univariate_selection(self, selection_id: str) -> UnivariateSelectionRecord:
        row = self._connection.execute(
            """select selection_id, source_run_id, version, content_hash, created_at, published_at
               from portfell.univariate_selections
               where workspace_id = 'default' and selection_id = %s""",
            (selection_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _selection(row, self._selection_members(selection_id))

    def list_univariate_selections(
        self, *, limit: int = 100
    ) -> tuple[UnivariateSelectionRecord, ...]:
        rows = self._connection.execute(
            """select selection_id, source_run_id, version, content_hash, created_at, published_at
               from portfell.univariate_selections where workspace_id = 'default'
               order by version desc, selection_id limit %s""",
            (_bounded_limit(limit),),
        ).fetchall()
        return tuple(_selection(row, self._selection_members(str(row[0]))) for row in rows)

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
    ) -> DecisionArtifactRecord:
        if objective not in MULTIVARIATE_OBJECTIVES:
            raise AppStateError(APP_STATE_CONFLICT)
        existing = self._connection.execute(
            """select decision_id, run_id, objective, winning_candidate_id, requested_method,
                      actual_method, available, production_eligible, reason, document, created_at
               from portfell.decision_artifacts where run_id = %s""",
            (run_id,),
        ).fetchone()
        if existing is not None:
            record = _decision(existing)
            expected = (
                objective,
                winning_candidate_id,
                requested_method,
                actual_method,
                available,
                production_eligible,
                reason,
                _json_object(document),
            )
            actual = (
                record.objective,
                record.winning_candidate_id,
                record.requested_method,
                record.actual_method,
                record.available,
                record.production_eligible,
                record.reason,
                record.document,
            )
            if actual != expected:
                raise AppStateError(APP_STATE_CONFLICT)
            return record
        try:
            self._connection.execute(
                """insert into portfell.decision_artifacts
                   (decision_id, run_id, objective, winning_candidate_id, requested_method,
                    actual_method, available, production_eligible, reason, document)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                (
                    decision_id,
                    run_id,
                    objective,
                    winning_candidate_id,
                    requested_method,
                    actual_method,
                    available,
                    production_eligible,
                    reason,
                    _json_dump(document),
                ),
            )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        return self.get_decision_artifact(run_id)

    def get_decision_artifact(self, run_id: str) -> DecisionArtifactRecord:
        row = self._connection.execute(
            """select decision_id, run_id, objective, winning_candidate_id, requested_method,
                      actual_method, available, production_eligible, reason, document, created_at
               from portfell.decision_artifacts where run_id = %s""",
            (run_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _decision(row)

    def set_ui_preference(self, key: str, value: JsonValue) -> UiPreferenceRecord:
        try:
            self._connection.execute(
                """insert into portfell.ui_preferences
                   (workspace_id, preference_key, value)
                   values ('default', %s, %s::jsonb)
                   on conflict (workspace_id, preference_key) do update
                   set value = excluded.value, updated_at = now()""",
                (key, _json_dump_value(value)),
            )
            self._connection.commit()
        except Exception as error:
            self._connection.rollback()
            raise AppStateError(APP_STATE_PERSISTENCE_FAILED) from error
        record = self.get_ui_preference(key)
        if record is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return record

    def get_ui_preference(self, key: str) -> UiPreferenceRecord | None:
        row = self._connection.execute(
            """select preference_key, value, updated_at from portfell.ui_preferences
               where workspace_id = 'default' and preference_key = %s""",
            (key,),
        ).fetchone()
        return None if row is None else _preference(row)

    def list_ui_preferences(self) -> tuple[UiPreferenceRecord, ...]:
        rows = self._connection.execute(
            """select preference_key, value, updated_at from portfell.ui_preferences
               where workspace_id = 'default' order by preference_key"""
        ).fetchall()
        return tuple(_preference(row) for row in rows)

    def _universe_members(self, universe_id: str) -> tuple[ListingIdentity, ...]:
        rows = self._connection.execute(
            """select isin, exchange, code from portfell.metadata_universe_members
               where universe_id = %s order by ordinal, isin, exchange, code""",
            (universe_id,),
        ).fetchall()
        return tuple(ListingIdentity(str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def _selection_members(self, selection_id: str) -> tuple[ListingIdentity, ...]:
        rows = self._connection.execute(
            """select isin, exchange, code from portfell.univariate_selection_members
               where selection_id = %s order by ordinal, isin, exchange, code""",
            (selection_id,),
        ).fetchall()
        return tuple(ListingIdentity(str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def _analysis_artifact(self, artifact_id: str) -> AnalysisArtifactRecord:
        row = self._connection.execute(
            """select artifact_id, run_id, artifact_type, content_hash, document, created_at
               from portfell.analysis_artifacts where artifact_id = %s""",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise AppStateError(APP_STATE_NOT_FOUND)
        return _artifact(row)


def _bounded_limit(limit: int) -> int:
    if limit < 1 or limit > 500:
        raise AppStateError(APP_STATE_CONFLICT)
    return limit


def _canonical_members(members: Sequence[ListingIdentity]) -> tuple[ListingIdentity, ...]:
    ordered = tuple(sorted(members))
    if len(ordered) != len(set(ordered)):
        raise AppStateError(APP_STATE_CONFLICT)
    if any(not part.strip() for member in ordered for part in (member.isin, member.exchange, member.code)):
        raise AppStateError(APP_STATE_CONFLICT)
    return ordered


def _json_dump(value: Mapping[str, JsonValue]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_dump_value(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_object(value: object) -> JsonObject:
    decoded: object = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, dict):
        raise AppStateError(APP_STATE_PERSISTENCE_FAILED)
    return cast(JsonObject, decoded)


def _json_value(value: object) -> JsonValue:
    decoded: object = json.loads(value) if isinstance(value, str) else value
    return cast(JsonValue, decoded)


def _snapshot(row: Sequence[object]) -> MarketSourceSnapshotRecord:
    return MarketSourceSnapshotRecord(
        snapshot_id=str(row[0]),
        source_fingerprint=str(row[1]),
        observed_at=cast(datetime, row[2]),
        created_at=cast(datetime, row[3]),
    )


def _universe(
    row: Sequence[object], members: tuple[ListingIdentity, ...]
) -> MetadataUniverseRecord:
    return MetadataUniverseRecord(
        universe_id=str(row[0]),
        source_snapshot_id=str(row[1]),
        version=int(cast(int, row[2])),
        content_hash=str(row[3]),
        created_at=cast(datetime, row[4]),
        published_at=cast(datetime, row[5]),
        members=members,
    )


def _run(row: Sequence[object]) -> AnalysisRunRecord:
    return AnalysisRunRecord(
        run_id=str(row[0]),
        stage=str(row[1]),
        status=str(row[2]),
        input_snapshot_id=str(row[3]),
        input_ref=str(row[4]),
        logical_hash=str(row[5]),
        algorithm_version=str(row[6]),
        failure_code=None if row[7] is None else str(row[7]),
        created_at=cast(datetime, row[8]),
        started_at=cast(datetime | None, row[9]),
        completed_at=cast(datetime | None, row[10]),
    )


def _artifact(row: Sequence[object]) -> AnalysisArtifactRecord:
    return AnalysisArtifactRecord(
        artifact_id=str(row[0]),
        run_id=str(row[1]),
        artifact_type=str(row[2]),
        content_hash=str(row[3]),
        document=_json_object(row[4]),
        created_at=cast(datetime, row[5]),
    )


def _selection(
    row: Sequence[object], members: tuple[ListingIdentity, ...]
) -> UnivariateSelectionRecord:
    return UnivariateSelectionRecord(
        selection_id=str(row[0]),
        source_run_id=str(row[1]),
        version=int(cast(int, row[2])),
        content_hash=str(row[3]),
        created_at=cast(datetime, row[4]),
        published_at=cast(datetime, row[5]),
        members=members,
    )


def _decision(row: Sequence[object]) -> DecisionArtifactRecord:
    return DecisionArtifactRecord(
        decision_id=str(row[0]),
        run_id=str(row[1]),
        objective=str(row[2]),
        winning_candidate_id=str(row[3]),
        requested_method=str(row[4]),
        actual_method=str(row[5]),
        available=bool(row[6]),
        production_eligible=bool(row[7]),
        reason=None if row[8] is None else str(row[8]),
        document=_json_object(row[9]),
        created_at=cast(datetime, row[10]),
    )


def _preference(row: Sequence[object]) -> UiPreferenceRecord:
    return UiPreferenceRecord(
        key=str(row[0]), value=_json_value(row[1]), updated_at=cast(datetime, row[2])
    )
