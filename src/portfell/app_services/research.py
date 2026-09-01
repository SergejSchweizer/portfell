"""Four-stage single-workspace application service over clean app state + MarketDataGateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import UTC, date, datetime
from typing import Protocol, cast
from uuid import uuid4

from portfell.app_services.analysis_executor import AnalysisJobExecutor
from portfell.app_services.market_data import AnalyticalMarketData
from portfell.app_services.multivariate_compute import (
    MULTIVARIATE_EXECUTION_VERSION,
    MultivariateComputation,
    compute_multivariate,
)
from portfell.app_services.research_compute import (
    ComputedRun,
    ComputedSelection,
    bivariate_source_id,
    compute_bivariate,
    compute_univariate,
    filtered_univariate_selection,
    full_univariate_selection,
    opaque_id,
    stable_hash,
    univariate_source_id,
)
from portfell.app_state.contracts import (
    AnalysisArtifactRecord,
    AnalysisJobRecord,
    AnalysisRunRecord,
    DecisionArtifactRecord,
    JsonValue,
    ListingIdentity,
    MarketSourceSnapshotRecord,
    MetadataUniverseRecord,
    UnivariateSelectionRecord,
)
from portfell.app_state.errors import APP_STATE_NOT_FOUND, AppStateError
from portfell.bivariate_statistics import BIVARIATE_STATISTICS_VERSION
from portfell.market_source.contracts import Listing, ListingKey
from portfell.market_source.errors import MarketSourceError
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.snapshot import build_market_source_snapshot
from portfell.table_io import JsonRow
from portfell.univariate_statistics import UNIVARIATE_CALCULATION_CONTRACT


class ApplicationMarketGateway(Protocol):
    def read_active_listings(self) -> tuple[Listing, ...]: ...

    def read_snapshot(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot: ...


class AppStatePort(Protocol):
    def put_market_source_snapshot(
        self, *, snapshot_id: str, source_fingerprint: str, observed_at: datetime
    ) -> MarketSourceSnapshotRecord: ...

    def get_market_source_snapshot(self, snapshot_id: str) -> MarketSourceSnapshotRecord: ...

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

    def create_or_get_active_job(
        self,
        *,
        job_id: str,
        stage: str,
        input_ref: str,
        requested_objective: str | None = None,
    ) -> AnalysisJobRecord: ...

    def claim_job(self, job_id: str, *, stale_before: datetime) -> AnalysisJobRecord: ...

    def link_job_run(self, job_id: str, run_id: str) -> AnalysisJobRecord: ...

    def complete_job(
        self, job_id: str, *, status: str, failure_code: str | None = None
    ) -> AnalysisJobRecord: ...

    def list_analysis_jobs(
        self, *, stage: str | None = None, status: str | None = None, limit: int = 100
    ) -> tuple[AnalysisJobRecord, ...]: ...


class ApplicationServiceError(RuntimeError):
    """Stable public application-service failure without SQL/credential detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ResearchApplicationService:
    """Canonical application service used by FastAPI and Plotly Dash replacement clients."""

    def __init__(
        self,
        state: AppStatePort,
        market_gateway: ApplicationMarketGateway,
        *,
        executor_factory: Callable[[], Executor] | None = None,
        analysis_job_executor: AnalysisJobExecutor | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state = state
        self._gateway = market_gateway
        self._market = AnalyticalMarketData(market_gateway)
        self._executor_factory = executor_factory or (lambda: ThreadPoolExecutor(max_workers=4))
        self._now = now or (lambda: datetime.now(UTC))
        self._analysis_jobs = analysis_job_executor or AnalysisJobExecutor(
            state, self._execute_analysis_job, now=self._now
        )

    # Metadata -----------------------------------------------------------------

    def metadata_options(self) -> JsonRow:
        listings = self._active_listings()
        return {
            "exchange": sorted({item.key.exchange for item in listings}),
            "instrument_type": sorted(
                {item.instrument_type for item in listings if item.instrument_type}
            ),
            "country": sorted({item.country for item in listings if item.country}),
            "currency": sorted({item.currency for item in listings if item.currency}),
            "active_listing_count": len(listings),
        }

    def active_listings(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> tuple[JsonRow, ...]:
        filters = {
            "exchange": _normalized(exchange),
            "instrument_type": _normalized(instrument_type),
            "country": _normalized(country),
            "currency": _normalized(currency),
        }
        return tuple(
            _listing_row(item)
            for item in self._active_listings()
            if _listing_matches(item, filters)
        )

    def create_metadata_universe(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> MetadataUniverseRecord:
        rows = self.active_listings(
            exchange=exchange,
            instrument_type=instrument_type,
            country=country,
            currency=currency,
        )
        if not rows:
            raise ApplicationServiceError("metadata_universe_empty")
        members = tuple(
            ListingIdentity(str(row["isin"]), str(row["exchange"]), str(row["code"]))
            for row in rows
        )
        listings_by_key = {item.key: item for item in self._active_listings()}
        selected = tuple(
            listings_by_key[ListingKey(member.isin, member.exchange, member.code)]
            for member in members
        )
        lineage = build_market_source_snapshot(
            listings=selected, quotes=(), dividends=(), splits=()
        )
        self._persist_source_snapshot(lineage.snapshot_id)
        content_hash = stable_hash(
            {
                "source_snapshot_id": lineage.snapshot_id,
                "members": [
                    {"isin": member.isin, "exchange": member.exchange, "code": member.code}
                    for member in members
                ],
            }
        )
        existing = next(
            (
                item
                for item in self._state.list_metadata_universes(limit=500)
                if item.content_hash == content_hash
            ),
            None,
        )
        if existing is not None:
            return existing
        history = self._state.list_metadata_universes(limit=500)
        version = max((item.version for item in history), default=0) + 1
        universe_id = opaque_id("metadata-universe", {"content_hash": content_hash})
        return self._state.create_metadata_universe(
            universe_id=universe_id,
            source_snapshot_id=lineage.snapshot_id,
            version=version,
            content_hash=content_hash,
            members=members,
        )

    def metadata_universe(self, universe_id: str) -> JsonRow:
        universe = self._state.get_metadata_universe(universe_id)
        listings = self._resolve_listings(universe.members)
        return {
            **_universe_row(universe),
            "items": [_listing_row(item) for item in listings],
        }

    def metadata_history(self) -> tuple[JsonRow, ...]:
        return tuple(_universe_row(item) for item in self._state.list_metadata_universes(limit=500))

    # Univariate ---------------------------------------------------------------

    def start_univariate_job(self, universe_id: str) -> JsonRow:
        self._state.get_metadata_universe(universe_id)
        return _job_row(self._submit_analysis_job("univariate", universe_id))

    def run_univariate(self, universe_id: str) -> JsonRow:
        universe = self._state.get_metadata_universe(universe_id)
        market = self._read_market(universe.members)
        source_id = univariate_source_id(
            universe_id=universe.universe_id, market_snapshot_id=market.snapshot_id
        )
        run_id = opaque_id("univariate-run", {"source_id": source_id})
        run = self._state.create_analysis_run(
            run_id=run_id,
            stage="univariate",
            status="running",
            input_snapshot_id=market.snapshot_id,
            input_ref=universe.universe_id,
            logical_hash=source_id,
            algorithm_version=UNIVARIATE_CALCULATION_CONTRACT,
        )
        if run.status == "succeeded":
            return self.run_detail(run.run_id)
        if run.status != "running":
            return _run_row(run)
        try:
            computed = compute_univariate(
                universe_id=universe.universe_id,
                market_snapshot_id=market.snapshot_id,
                quote_rows=market.quotes,
                dividend_rows=market.dividends,
            )
            self._put_artifact(run.run_id, "univariate_rows", {"items": list(computed.rows)})
            completed = self._state.transition_analysis_run(run_id=run.run_id, status="succeeded")
            return self.run_detail(completed.run_id)
        except Exception as error:
            self._fail_run(run.run_id, error)
            raise _public_error(error) from error

    def create_univariate_selection(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> UnivariateSelectionRecord:
        run = self._require_succeeded_run(run_id, "univariate")
        computed = self._computed_run(run, "univariate_rows")
        try:
            selection = (
                full_univariate_selection(computed)
                if predicates is None
                else filtered_univariate_selection(computed, predicates)
            )
        except Exception as error:
            raise _public_error(error) from error
        members = tuple(_identity_from_member_id(item) for item in selection.member_ids)
        content_hash = stable_hash(
            {
                "source_run_id": run.run_id,
                "members": list(selection.member_ids),
                "predicates": [predicate.as_text() for predicate in selection.predicates],
            }
        )
        existing = next(
            (
                item
                for item in self._state.list_univariate_selections(limit=500)
                if item.content_hash == content_hash
            ),
            None,
        )
        if existing is not None:
            return existing
        history = self._state.list_univariate_selections(limit=500)
        version = max((item.version for item in history), default=0) + 1
        return self._state.create_univariate_selection(
            selection_id=selection.selection_id,
            source_run_id=run.run_id,
            version=version,
            content_hash=content_hash,
            members=members,
        )

    # Bivariate ----------------------------------------------------------------

    def start_bivariate_job(self, selection_id: str) -> JsonRow:
        self._state.get_univariate_selection(selection_id)
        return _job_row(self._submit_analysis_job("bivariate", selection_id))

    def run_bivariate(self, selection_id: str) -> JsonRow:
        persisted = self._state.get_univariate_selection(selection_id)
        source_run = self._require_succeeded_run(persisted.source_run_id, "univariate")
        source_computed = self._computed_run(source_run, "univariate_rows")
        member_ids = tuple(_member_id(item) for item in persisted.members)
        selected_rows = tuple(
            row for row in source_computed.rows if _row_member_id(row) in set(member_ids)
        )
        selection = ComputedSelection(
            selection_id=persisted.selection_id,
            source_run_id=source_run.run_id,
            member_ids=member_ids,
            predicates=(),
            rows=selected_rows,
        )
        market = self._read_market(persisted.members)
        source_id = bivariate_source_id(
            selection_id=selection.selection_id,
            member_ids=selection.member_ids,
            market_snapshot_id=market.snapshot_id,
        )
        run_id = opaque_id("bivariate-run", {"source_id": source_id})
        run = self._state.create_analysis_run(
            run_id=run_id,
            stage="bivariate",
            status="running",
            input_snapshot_id=market.snapshot_id,
            input_ref=persisted.selection_id,
            logical_hash=source_id,
            algorithm_version=BIVARIATE_STATISTICS_VERSION,
        )
        if run.status == "succeeded":
            return self.run_detail(run.run_id)
        if run.status != "running":
            return _run_row(run)
        try:
            computed = compute_bivariate(
                selection=selection,
                market_snapshot_id=market.snapshot_id,
                quote_rows=market.quotes,
            )
            self._put_artifact(run.run_id, "bivariate_rows", {"items": list(computed.rows)})
            completed = self._state.transition_analysis_run(run_id=run.run_id, status="succeeded")
            return self.run_detail(completed.run_id)
        except Exception as error:
            self._fail_run(run.run_id, error)
            raise _public_error(error) from error

    # Multivariate -------------------------------------------------------------

    def start_multivariate_job(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> JsonRow:
        if objective not in {"return_risk", "return_drawdown", "minimum_risk"}:
            raise ApplicationServiceError("invalid_multivariate_objective")
        self._state.get_univariate_selection(selection_id)
        bivariate = self._state.get_analysis_run(bivariate_run_id)
        if bivariate.stage != "bivariate" or bivariate.input_ref != selection_id:
            raise ApplicationServiceError("bivariate_dependency_mismatch")
        return _job_row(
            self._submit_analysis_job(
                "multivariate", bivariate_run_id, requested_objective=objective
            )
        )

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> JsonRow:
        if objective not in {"return_risk", "return_drawdown", "minimum_risk"}:
            raise ApplicationServiceError("invalid_multivariate_objective")
        selection = self._state.get_univariate_selection(selection_id)
        univariate_run = self._require_succeeded_run(selection.source_run_id, "univariate")
        bivariate_run = self._require_succeeded_run(bivariate_run_id, "bivariate")
        if bivariate_run.input_ref != selection.selection_id:
            raise ApplicationServiceError("bivariate_dependency_mismatch")
        market = self._read_market(selection.members)
        if market.snapshot_id != bivariate_run.input_snapshot_id:
            raise ApplicationServiceError("market_source_snapshot_changed")
        logical_hash = stable_hash(
            {
                "universe_id": univariate_run.input_ref,
                "univariate_run_id": univariate_run.run_id,
                "selection_id": selection.selection_id,
                "bivariate_run_id": bivariate_run.run_id,
                "market_snapshot_id": market.snapshot_id,
                "objective": objective,
                "execution_version": MULTIVARIATE_EXECUTION_VERSION,
            }
        )
        run_id = opaque_id("multivariate-run", {"logical_hash": logical_hash})
        run = self._state.create_analysis_run(
            run_id=run_id,
            stage="multivariate",
            status="running",
            input_snapshot_id=market.snapshot_id,
            input_ref=bivariate_run.run_id,
            logical_hash=logical_hash,
            algorithm_version=MULTIVARIATE_EXECUTION_VERSION,
        )
        if run.status == "succeeded":
            return self.run_detail(run.run_id)
        if run.status != "running":
            return _run_row(run)
        source_computed = self._computed_run(univariate_run, "univariate_rows")
        selected_ids = {_member_id(item) for item in selection.members}
        selected_rows = tuple(
            row for row in source_computed.rows if _row_member_id(row) in selected_ids
        )
        listing_metadata = tuple(_listing_row(item) for item in market.listings)
        try:
            with self._executor_factory() as executor:
                computation = compute_multivariate(
                    universe_id=univariate_run.input_ref,
                    univariate_run_id=univariate_run.run_id,
                    selection_id=selection.selection_id,
                    bivariate_run_id=bivariate_run.run_id,
                    market_snapshot_id=market.snapshot_id,
                    selected_rows=selected_rows,
                    listing_metadata=listing_metadata,
                    quote_rows=market.quotes,
                    dividend_rows=market.dividends,
                    objective=objective,
                    executor=executor,
                )
            self._persist_multivariate(run.run_id, computation)
            completed = self._state.transition_analysis_run(run_id=run.run_id, status="succeeded")
            return self.run_detail(completed.run_id)
        except Exception as error:
            self._fail_run(run.run_id, error)
            raise _public_error(error) from error

    # Shared reads -------------------------------------------------------------

    def run_detail(self, run_id: str) -> JsonRow:
        run = self._state.get_analysis_run(run_id)
        artifacts = self._state.list_analysis_artifacts(run.run_id)
        row = _run_row(run)
        row["artifacts"] = {artifact.artifact_type: artifact.document for artifact in artifacts}
        if run.stage == "multivariate" and run.status == "succeeded":
            try:
                decision = self._state.get_decision_artifact(run.run_id)
            except AppStateError as error:
                if error.code != APP_STATE_NOT_FOUND:
                    raise
            else:
                row["decision"] = _decision_row(decision)
        return row

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]:
        return tuple(
            _run_row(item) for item in self._state.list_analysis_runs(stage=stage, limit=limit)
        )

    def workflow_state(self) -> JsonRow:
        universes = self._state.list_metadata_universes(limit=1)
        selections = self._state.list_univariate_selections(limit=1)
        stages: dict[str, JsonRow | None] = {}
        for stage in ("univariate", "bivariate", "multivariate"):
            runs = self._state.list_analysis_runs(stage=stage, limit=1)
            stages[stage] = None if not runs else _run_row(runs[0])
        universe = universes[0] if universes else None
        selection = selections[0] if selections else None
        return {
            "workspace_id": "default",
            "metadata_universe": None if universe is None else _universe_row(universe),
            "univariate_selection": None if selection is None else _selection_row(selection),
            "stages": stages,
        }

    def start_background_jobs(self) -> None:
        self._analysis_jobs.recover()

    def stop_background_jobs(self) -> None:
        self._analysis_jobs.close()

    # Internal -----------------------------------------------------------------

    def _submit_analysis_job(
        self, stage: str, input_ref: str, *, requested_objective: str | None = None
    ) -> AnalysisJobRecord:
        job = self._state.create_or_get_active_job(
            job_id=f"analysis-job-{uuid4().hex}",
            stage=stage,
            input_ref=input_ref,
            requested_objective=requested_objective,
        )
        self._analysis_jobs.submit(job)
        return job

    def _execute_analysis_job(self, job: AnalysisJobRecord) -> JsonRow:
        if job.stage == "univariate":
            return self.run_univariate(job.input_ref)
        if job.stage == "bivariate":
            return self.run_bivariate(job.input_ref)
        if job.stage == "multivariate":
            run = self._state.get_analysis_run(job.input_ref)
            return self.run_multivariate(
                selection_id=run.input_ref,
                bivariate_run_id=run.run_id,
                objective=job.requested_objective or "return_risk",
            )
        raise ApplicationServiceError("analysis_job_stage_invalid")

    def _active_listings(self) -> tuple[Listing, ...]:
        try:
            rows = tuple(sorted(self._gateway.read_active_listings(), key=lambda item: item.key))
        except Exception as error:
            raise _public_error(error) from error
        if any(not item.is_active for item in rows):
            raise ApplicationServiceError("market_source_contract_mismatch")
        return rows

    def _resolve_listings(self, members: Sequence[ListingIdentity]) -> tuple[Listing, ...]:
        keys = tuple(ListingKey(item.isin, item.exchange, item.code) for item in members)
        try:
            source = self._gateway.read_snapshot(keys, start=date.min, end=date.max)
        except Exception as error:
            raise _public_error(error) from error
        if {item.key for item in source.listings} != set(keys):
            raise ApplicationServiceError("market_source_contract_mismatch")
        return tuple(sorted(source.listings, key=lambda item: item.key))

    def _read_market(self, members: Sequence[ListingIdentity]):
        try:
            market = self._market.read(members)
            self._persist_source_snapshot(market.snapshot_id)
            return market
        except Exception as error:
            raise _public_error(error) from error

    def _persist_source_snapshot(self, snapshot_id: str) -> None:
        self._state.put_market_source_snapshot(
            snapshot_id=snapshot_id,
            source_fingerprint=snapshot_id,
            observed_at=self._now(),
        )

    def _require_succeeded_run(self, run_id: str, stage: str) -> AnalysisRunRecord:
        run = self._state.get_analysis_run(run_id)
        if run.stage != stage or run.status != "succeeded":
            raise ApplicationServiceError(f"{stage}_run_not_ready")
        return run

    def _computed_run(self, run: AnalysisRunRecord, artifact_type: str) -> ComputedRun:
        artifact = self._artifact(run.run_id, artifact_type)
        raw_items = artifact.document.get("items")
        if not isinstance(raw_items, list):
            raise ApplicationServiceError("analysis_artifact_invalid")
        rows = tuple(cast(JsonRow, item) for item in raw_items if isinstance(item, dict))
        if len(rows) != len(raw_items):
            raise ApplicationServiceError("analysis_artifact_invalid")
        return ComputedRun(
            run_id=run.run_id,
            source_id=run.logical_hash,
            algorithm_version=run.algorithm_version,
            rows=rows,
        )

    def _artifact(self, run_id: str, artifact_type: str) -> AnalysisArtifactRecord:
        matches = [
            item
            for item in self._state.list_analysis_artifacts(run_id)
            if item.artifact_type == artifact_type
        ]
        if len(matches) != 1:
            raise ApplicationServiceError("analysis_artifact_not_found")
        return matches[0]

    def _put_artifact(self, run_id: str, artifact_type: str, document: JsonRow) -> None:
        content_hash = stable_hash(cast(Mapping[str, object], document))
        artifact_id = opaque_id(
            "analysis-artifact",
            {"run_id": run_id, "artifact_type": artifact_type, "content_hash": content_hash},
        )
        self._state.put_analysis_artifact(
            artifact_id=artifact_id,
            run_id=run_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            document=cast(Mapping[str, JsonValue], document),
        )

    def _persist_multivariate(self, run_id: str, computation: MultivariateComputation) -> None:
        for artifact_type, document in sorted(computation.documents.items()):
            normalized = document if isinstance(document, dict) else {"items": document}
            self._put_artifact(run_id, artifact_type, normalized)
        decision = computation.decision
        decision_id = opaque_id(
            "decision-artifact",
            {
                "run_id": run_id,
                "objective": decision.objective,
                "winner": decision.winning_candidate_id,
            },
        )
        self._state.put_decision_artifact(
            decision_id=decision_id,
            run_id=run_id,
            objective=decision.objective,
            winning_candidate_id=decision.winning_candidate_id,
            requested_method=decision.requested_method,
            actual_method=decision.actual_method,
            available=decision.available,
            production_eligible=decision.production_eligible,
            reason=decision.reason,
            document=cast(Mapping[str, JsonValue], decision.document),
        )

    def _fail_run(self, run_id: str, error: Exception) -> None:
        try:
            self._state.transition_analysis_run(
                run_id=run_id, status="failed", failure_code=_failure_code(error)
            )
        except Exception:
            # Preserve the original typed compute/source error and never replace it with
            # persistence internals while the clean DB is already unhealthy.
            return


def _normalized(value: str | None) -> str | None:
    cleaned = None if value is None else value.strip()
    return None if not cleaned else cleaned.casefold()


def _listing_matches(item: Listing, filters: Mapping[str, str | None]) -> bool:
    values = {
        "exchange": item.key.exchange,
        "instrument_type": item.instrument_type,
        "country": item.country,
        "currency": item.currency,
    }
    return all(
        expected is None or (values[name] is not None and str(values[name]).casefold() == expected)
        for name, expected in filters.items()
    )


def _listing_row(item: Listing) -> JsonRow:
    return {
        "isin": item.key.isin,
        "exchange": item.key.exchange,
        "code": item.key.code,
        "name": item.name,
        "instrument_type": item.instrument_type,
        "country": item.country,
        "currency": item.currency,
        "is_active": item.is_active,
    }


def _universe_row(item: MetadataUniverseRecord) -> JsonRow:
    return {
        "universe_id": item.universe_id,
        "version": item.version,
        "source_snapshot_id": item.source_snapshot_id,
        "member_count": len(item.members),
        "created_at": item.created_at.isoformat(),
        "published_at": item.published_at.isoformat(),
        "members": [
            {"isin": member.isin, "exchange": member.exchange, "code": member.code}
            for member in item.members
        ],
    }


def _selection_row(item: UnivariateSelectionRecord) -> JsonRow:
    return {
        "selection_id": item.selection_id,
        "source_run_id": item.source_run_id,
        "version": item.version,
        "member_count": len(item.members),
        "created_at": item.created_at.isoformat(),
        "published_at": item.published_at.isoformat(),
        "members": [
            {"isin": member.isin, "exchange": member.exchange, "code": member.code}
            for member in item.members
        ],
    }


def _run_row(item: AnalysisRunRecord) -> JsonRow:
    return {
        "run_id": item.run_id,
        "stage": item.stage,
        "status": item.status,
        "input_snapshot_id": item.input_snapshot_id,
        "input_ref": item.input_ref,
        "logical_hash": item.logical_hash,
        "algorithm_version": item.algorithm_version,
        "failure_code": item.failure_code,
        "created_at": item.created_at.isoformat(),
        "started_at": None if item.started_at is None else item.started_at.isoformat(),
        "completed_at": None if item.completed_at is None else item.completed_at.isoformat(),
    }


def _job_row(item: AnalysisJobRecord) -> JsonRow:
    return {
        "job_id": item.job_id,
        "stage": item.stage,
        "input_ref": item.input_ref,
        "requested_objective": item.requested_objective,
        "status": item.status,
        "run_id": item.run_id,
        "progress_current": item.progress_current,
        "progress_total": item.progress_total,
        "progress_phase": item.progress_phase,
        "attempt": item.attempt,
        "failure_code": item.failure_code,
        "created_at": item.created_at.isoformat(),
        "started_at": None if item.started_at is None else item.started_at.isoformat(),
        "completed_at": None if item.completed_at is None else item.completed_at.isoformat(),
    }


def _decision_row(item: DecisionArtifactRecord) -> JsonRow:
    return {
        "decision_id": item.decision_id,
        "run_id": item.run_id,
        "objective": item.objective,
        "winning_candidate_id": item.winning_candidate_id,
        "requested_method": item.requested_method,
        "actual_method": item.actual_method,
        "available": item.available,
        "production_eligible": item.production_eligible,
        "reason": item.reason,
        "document": item.document,
        "created_at": item.created_at.isoformat(),
    }


def _member_id(item: ListingIdentity) -> str:
    return f"{item.isin}:{item.exchange}:{item.code}"


def _row_member_id(row: Mapping[str, object]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def _identity_from_member_id(value: str) -> ListingIdentity:
    parts = value.split(":")
    if len(parts) != 3 or not all(parts):
        raise ApplicationServiceError("listing_identity_invalid")
    return ListingIdentity(parts[0], parts[1], parts[2])


def _failure_code(error: Exception) -> str:
    if isinstance(error, ApplicationServiceError):
        return error.code
    if isinstance(error, AppStateError):
        return error.code
    if isinstance(error, MarketSourceError):
        return error.code
    if isinstance(error, ValueError):
        text = str(error)
        if text and all(character.isalnum() or character in {"_", "-"} for character in text):
            return text
    return "analysis_compute_failed"


def _public_error(error: Exception) -> ApplicationServiceError:
    if isinstance(error, ApplicationServiceError):
        return error
    return ApplicationServiceError(_failure_code(error))
