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
    AnalysisArtifactItem,
    AnalysisArtifactItemRecord,
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
from portfell.gold_pair_stats import DEFAULT_MAX_PAIR_COUNT, build_pair_plan
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

    def publish_row_backed_analysis_artifact(
        self,
        *,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        content_hash: str,
        document: Mapping[str, JsonValue],
        items: Sequence[AnalysisArtifactItem],
    ) -> AnalysisArtifactRecord: ...

    def list_analysis_artifact_items(
        self, artifact_id: str, *, offset: int = 0, limit: int = 100
    ) -> tuple[AnalysisArtifactItemRecord, ...]: ...

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

    def update_job_progress(
        self, job_id: str, *, current: int, total: int | None, phase: str
    ) -> AnalysisJobRecord: ...

    def list_analysis_jobs(
        self, *, stage: str | None = None, status: str | None = None, limit: int = 100
    ) -> tuple[AnalysisJobRecord, ...]: ...

    def get_analysis_job(self, job_id: str) -> AnalysisJobRecord: ...


class ApplicationServiceError(RuntimeError):
    """Stable public application-service failure without SQL/credential detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CoalescedProgress:
    """Persist monotone progress at most once per percentage bucket."""

    def __init__(self, state: AppStatePort, job_id: str, total: int, phase: str) -> None:
        self._state = state
        self._job_id = job_id
        self._total = max(0, total)
        self._phase = phase
        self._last_bucket = -1

    def write(self, current: int) -> None:
        bounded = min(self._total, max(0, current))
        bucket = 100 if self._total == 0 else (bounded * 100) // self._total
        if bucket == self._last_bucket and bounded != self._total:
            return
        self._last_bucket = bucket
        self._state.update_job_progress(
            self._job_id, current=bounded, total=self._total, phase=self._phase
        )


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

    def create_universe_and_start_univariate(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> JsonRow:
        """Commit one Metadata universe and immediately enqueue its full-Universe analysis."""
        universe = self.create_metadata_universe(
            exchange=exchange,
            instrument_type=instrument_type,
            country=country,
            currency=currency,
        )
        return {
            "universe": _universe_row(universe),
            "job": self.start_univariate_job(universe.universe_id),
        }

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

    def run_univariate(self, universe_id: str, *, job_id: str | None = None) -> JsonRow:
        universe = self._state.get_metadata_universe(universe_id)
        market = self._read_market(universe.members)
        if job_id is not None:
            self._state.update_job_progress(
                job_id,
                current=0,
                total=len(universe.members),
                phase="members",
            )
            progress = CoalescedProgress(self._state, job_id, len(universe.members), "members")
        else:
            progress = None
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

            def on_progress(current: int) -> None:
                if progress is not None:
                    progress.write(current)

            computed = compute_univariate(
                universe_id=universe.universe_id,
                market_snapshot_id=market.snapshot_id,
                quote_rows=market.quotes,
                dividend_rows=market.dividends,
                on_progress=None if job_id is None else on_progress,
            )
            self._put_row_backed_artifact(
                run.run_id,
                "univariate.rows@v2",
                computed.rows,
                summary={
                    "universe_id": universe.universe_id,
                    "market_snapshot_id": market.snapshot_id,
                    "available_count": sum(
                        row.get("availability_reason") == "ok" for row in computed.rows
                    ),
                    "unavailable_count": sum(
                        row.get("availability_reason") != "ok" for row in computed.rows
                    ),
                },
            )
            # v3 is additive: v2 remains available to existing consumers while
            # metric-card pages can opt into the enriched catalog atomically.
            self._put_row_backed_artifact(
                run.run_id,
                "univariate.rows@v3",
                computed.rows,
                summary={
                    "universe_id": universe.universe_id,
                    "market_snapshot_id": market.snapshot_id,
                    "metric_contract": "univariate.metrics.v3",
                    "available_count": sum(
                        row.get("availability_reason") == "ok" for row in computed.rows
                    ),
                    "unavailable_count": sum(
                        row.get("availability_reason") != "ok" for row in computed.rows
                    ),
                },
            )
            if job_id is not None:
                self._state.update_job_progress(
                    job_id,
                    current=len(universe.members),
                    total=len(universe.members),
                    phase="members",
                )
            completed = self._state.transition_analysis_run(run_id=run.run_id, status="succeeded")
            return self.run_detail(completed.run_id)
        except Exception as error:
            self._fail_run(run.run_id, error)
            raise _public_error(error) from error

    def create_univariate_selection(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> UnivariateSelectionRecord:
        run = self._require_succeeded_run(run_id, "univariate")
        computed = self._computed_run(run, "univariate.rows@v2")
        try:
            selection = (
                full_univariate_selection(computed)
                if predicates is None
                else filtered_univariate_selection(computed, predicates)
            )
            if predicates is not None:
                if not selection.rows:
                    raise ApplicationServiceError("univariate_selection_empty")
                if any(row.get("availability_reason") != "ok" for row in selection.rows):
                    raise ApplicationServiceError("univariate_selection_unavailable")
        except Exception as error:
            if isinstance(error, ApplicationServiceError):
                raise
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

    def create_selection_and_start_downstream(
        self,
        run_id: str,
        *,
        predicates: Sequence[Mapping[str, object]] | None = None,
    ) -> JsonRow:
        """Persist one exact selection and enqueue its Bivariate dependency once."""
        selection = self.create_univariate_selection(run_id, predicates=predicates)
        return {
            "selection": _selection_row(selection),
            "job": self.start_bivariate_job(selection.selection_id),
        }

    # Bivariate ----------------------------------------------------------------

    def start_bivariate_job(self, selection_id: str) -> JsonRow:
        self._state.get_univariate_selection(selection_id)
        list_jobs = getattr(self._state, "list_analysis_jobs", None)
        if callable(list_jobs):
            completed_jobs = cast(Callable[..., tuple[AnalysisJobRecord, ...]], list_jobs)(
                stage="bivariate", status="succeeded", limit=500
            )
            for completed in completed_jobs:
                if completed.input_ref == selection_id:
                    return _job_row(completed)
        return _job_row(self._submit_analysis_job("bivariate", selection_id))

    def run_bivariate(self, selection_id: str, *, job_id: str | None = None) -> JsonRow:
        persisted = self._state.get_univariate_selection(selection_id)
        source_run = self._require_succeeded_run(persisted.source_run_id, "univariate")
        source_computed = self._computed_run(source_run, "univariate.rows@v2")
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
            pair_total = len(member_ids) * (len(member_ids) - 1) // 2
            progress: CoalescedProgress | None = None

            def on_progress(current: int, total: int) -> None:
                if progress is not None:
                    progress.write(current)

            if job_id is not None:
                self._state.update_job_progress(job_id, current=0, total=pair_total, phase="pairs")
                progress = CoalescedProgress(self._state, job_id, pair_total, "pairs")
            computed = compute_bivariate(
                selection=selection,
                market_snapshot_id=market.snapshot_id,
                quote_rows=market.quotes,
                on_progress=None if job_id is None else on_progress,
            )
            self._put_row_backed_artifact(
                run.run_id,
                "bivariate.rows@v2",
                computed.rows,
                summary={
                    "selection_id": selection.selection_id,
                    "market_snapshot_id": market.snapshot_id,
                    "candidate_pair_count": pair_total,
                    "eligible_count": len(computed.rows),
                    "unavailable_count": max(0, pair_total - len(computed.rows)),
                },
            )
            if job_id is not None:
                self._state.update_job_progress(
                    job_id, current=pair_total, total=pair_total, phase="pairs"
                )
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
        list_jobs = getattr(self._state, "list_analysis_jobs", None)
        if callable(list_jobs):
            completed_jobs = cast(Callable[..., tuple[AnalysisJobRecord, ...]], list_jobs)(
                stage="multivariate", status="succeeded", limit=500
            )
            for completed in completed_jobs:
                if (
                    completed.input_ref == bivariate_run_id
                    and completed.requested_objective == objective
                ):
                    return _job_row(completed)
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
        job_id: str | None = None,
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
        source_computed = self._computed_run(univariate_run, "univariate.rows@v2")
        selected_ids = {_member_id(item) for item in selection.members}
        selected_rows = tuple(
            row for row in source_computed.rows if _row_member_id(row) in selected_ids
        )
        listing_metadata = tuple(_listing_row(item) for item in market.listings)
        try:

            def on_phase(current: int, phase: str) -> None:
                if job_id is not None:
                    self._state.update_job_progress(job_id, current=current, total=8, phase=phase)

            if job_id is not None:
                self._state.update_job_progress(job_id, current=0, total=8, phase="inputs")
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
                    on_phase=None if job_id is None else on_phase,
                )
            self._persist_multivariate(run.run_id, computation)
            if job_id is not None:
                self._state.update_job_progress(
                    job_id, current=7, total=8, phase="artifact_persistence"
                )
            completed = self._state.transition_analysis_run(run_id=run.run_id, status="succeeded")
            if job_id is not None:
                self._state.update_job_progress(job_id, current=8, total=8, phase="complete")
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
        if run.stage == "bivariate" and "bivariate.rows@v2" in row["artifacts"]:
            # Keep the historical artifact key readable for older API clients. New
            # Dash reads use the bounded row-backed contract exclusively.
            row["artifacts"]["bivariate_rows"] = row["artifacts"]["bivariate.rows@v2"]
        return row

    def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> JsonRow:
        """Return a bounded persisted result preview without hydrating the full artifact."""
        if limit < 1 or limit > 500:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        run = self._require_succeeded_run(run_id, "univariate")
        artifact = self._artifact(run.run_id, "univariate.rows@v2")
        if artifact.document.get("storage") != "row_items":
            raise ApplicationServiceError("analysis_artifact_invalid")
        item_count = artifact.document.get("item_count")
        summary = artifact.document.get("summary")
        if not isinstance(item_count, int) or item_count < 0 or not isinstance(summary, dict):
            raise ApplicationServiceError("analysis_artifact_invalid")
        items = self._state.list_analysis_artifact_items(artifact.artifact_id, limit=limit)
        rows = [item.document for item in items]
        return {
            "run": _run_row(run),
            "item_count": item_count,
            "summary": cast(JsonRow, summary),
            "rows": cast(list[JsonValue], rows),
        }

    def univariate_summary(self, run_id: str) -> JsonRow:
        """Read only the small manifest and summary for a completed Univariate run."""
        run = self._require_succeeded_run(run_id, "univariate")
        artifact = self._artifact(run.run_id, "univariate.rows@v2")
        if artifact.document.get("storage") != "row_items":
            raise ApplicationServiceError("analysis_artifact_invalid")
        item_count = artifact.document.get("item_count")
        summary = artifact.document.get("summary")
        if not isinstance(item_count, int) or item_count < 0 or not isinstance(summary, dict):
            raise ApplicationServiceError("analysis_artifact_invalid")
        return {
            "run": _run_row(run),
            "item_count": item_count,
            "summary": cast(JsonRow, summary),
        }

    def univariate_page(self, run_id: str, *, offset: int = 0, limit: int = 100) -> JsonRow:
        """Read one deterministic bounded page from row-backed Univariate output."""
        if offset < 0 or limit < 1 or limit > 100:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        summary = self.univariate_summary(run_id)
        artifact = self._artifact(run_id, "univariate.rows@v2")
        items = self._state.list_analysis_artifact_items(
            artifact.artifact_id, offset=offset, limit=limit
        )
        return {
            **summary,
            "offset": offset,
            "limit": limit,
            "rows": cast(list[JsonValue], [item.document for item in items]),
        }

    def univariate_chart_sample(self, run_id: str, *, limit: int = 500) -> JsonRow:
        """Read a deterministic bounded chart sample without a market read or calculation."""
        if limit < 1 or limit > 500:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        page = self.univariate_page(run_id, limit=min(limit, 100))
        rows = list(cast(list[JsonValue], page["rows"]))
        summary = self.univariate_summary(run_id)
        count = int(summary["item_count"])
        for offset in range(100, min(count, limit), 100):
            rows.extend(
                cast(
                    list[JsonValue],
                    self.univariate_page(run_id, offset=offset, limit=min(100, limit - len(rows)))[
                        "rows"
                    ],
                )
            )
        return {"run": summary["run"], "item_count": count, "rows": rows[:limit]}

    def univariate_filter_preview(
        self,
        run_id: str,
        *,
        predicates: Sequence[Mapping[str, object]],
        offset: int = 0,
        limit: int = 100,
        chart_limit: int = 500,
    ) -> JsonRow:
        """Evaluate predicates over persisted rows only; this method never writes or computes."""
        if offset < 0 or limit < 1 or limit > 100 or chart_limit < 1 or chart_limit > 500:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        run = self._require_succeeded_run(run_id, "univariate")
        computed = self._computed_run(run, "univariate.rows@v2")
        try:
            selection = filtered_univariate_selection(computed, predicates)
        except Exception as error:
            raise _public_error(error) from error
        matching = tuple(selection.rows)
        available = tuple(row for row in matching if row.get("availability_reason") == "ok")
        unavailable_count = len(matching) - len(available)
        member_count = len({_row_member_id(row) for row in available})
        pair_plan = build_pair_plan(member_count, max_pair_count=DEFAULT_MAX_PAIR_COUNT)
        page_rows = available[offset : offset + limit]
        return {
            "run": _run_row(run),
            "predicates": [
                str(row.get("metric")) + str(row.get("operator")) + str(row.get("value"))
                for row in predicates
            ],
            "matching_count": len(matching),
            "available_count": member_count,
            "unavailable_count": unavailable_count,
            "candidate_pair_count": pair_plan.theoretical_pair_count,
            "downstream_runnable": bool(available) and pair_plan.accepted and member_count >= 2,
            "offset": offset,
            "limit": limit,
            "rows": cast(list[JsonValue], list(page_rows)),
            "chart_rows": cast(list[JsonValue], list(available[:chart_limit])),
        }

    def bivariate_summary(self, run_id: str) -> JsonRow:
        """Read the bounded pair manifest and summary for a completed run."""
        run = self._require_succeeded_run(run_id, "bivariate")
        artifact = self._bivariate_artifact(run_id)
        document = artifact.document
        if document.get("storage") == "row_items":
            item_count = document.get("item_count")
            summary = document.get("summary")
            if not isinstance(item_count, int) or not isinstance(summary, dict):
                raise ApplicationServiceError("analysis_artifact_invalid")
            return {
                "run": _run_row(run),
                "item_count": item_count,
                "summary": cast(JsonRow, summary),
            }
        raw_items = document.get("items")
        if not isinstance(raw_items, list):
            raise ApplicationServiceError("analysis_artifact_invalid")
        return {
            "run": _run_row(run),
            "item_count": len(raw_items),
            "summary": {"eligible_count": len(raw_items)},
        }

    def bivariate_page(self, run_id: str, *, offset: int = 0, limit: int = 100) -> JsonRow:
        """Read at most one hundred deterministic persisted pair rows."""
        if offset < 0 or limit < 1 or limit > 100:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        summary = self.bivariate_summary(run_id)
        artifact = self._bivariate_artifact(run_id)
        if artifact.document.get("storage") == "row_items":
            items = self._state.list_analysis_artifact_items(
                artifact.artifact_id, offset=offset, limit=limit
            )
            rows = [item.document for item in items]
        else:
            raw_items = artifact.document.get("items")
            rows = list(raw_items[offset : offset + limit]) if isinstance(raw_items, list) else []
        return {
            **summary,
            "offset": offset,
            "limit": limit,
            "rows": cast(list[JsonValue], rows),
        }

    def bivariate_chart_sample(self, run_id: str, *, limit: int = 1000) -> JsonRow:
        """Read a deterministic bounded pair sample for chart rendering."""
        if limit < 1 or limit > 1000:
            raise ApplicationServiceError("analysis_artifact_page_invalid")
        summary = self.bivariate_summary(run_id)
        artifact = self._bivariate_artifact(run_id)
        if artifact.document.get("storage") == "row_items":
            rows: list[JsonValue] = []
            count = int(summary["item_count"])
            for offset in range(0, min(count, limit), 100):
                rows.extend(
                    cast(
                        list[JsonValue],
                        self.bivariate_page(
                            run_id, offset=offset, limit=min(100, limit - len(rows))
                        )["rows"],
                    )
                )
            return {"run": summary["run"], "item_count": count, "rows": rows[:limit]}
        raw_items = artifact.document.get("items")
        rows = raw_items[:limit] if isinstance(raw_items, list) else []
        return {"run": summary["run"], "item_count": len(rows), "rows": rows}

    def multivariate_summary(self, run_id: str) -> JsonRow:
        """Return only run/decision identity and an artifact-name manifest."""
        run = self._require_succeeded_run(run_id, "multivariate")
        artifacts = self._state.list_analysis_artifacts(run_id)
        result: JsonRow = {
            "run": _run_row(run),
            "artifact_types": [item.artifact_type for item in artifacts],
        }
        try:
            result["decision"] = _decision_row(self._state.get_decision_artifact(run_id))
        except AppStateError as error:
            if error.code != APP_STATE_NOT_FOUND:
                raise
        return result

    def multivariate_artifact(self, run_id: str, artifact_type: str) -> JsonRow:
        """Read one named Multivariate artifact on demand."""
        run = self._require_succeeded_run(run_id, "multivariate")
        return cast(JsonRow, self._artifact(run.run_id, artifact_type).document)

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]:
        return tuple(
            _run_row(item) for item in self._state.list_analysis_runs(stage=stage, limit=limit)
        )

    def workflow_state(self) -> JsonRow:
        universes = self._state.list_metadata_universes(limit=1)
        project_history = self._state.list_metadata_universes(limit=500)
        selections = self._state.list_univariate_selections(limit=1)
        stages: dict[str, JsonRow | None] = {}
        history: dict[str, list[JsonRow]] = {}
        for stage in ("univariate", "bivariate", "multivariate"):
            runs = self._state.list_analysis_runs(stage=stage, limit=20)
            stages[stage] = None if not runs else _run_row(runs[0])
            history[stage] = [_run_row(item) for item in runs]
        universe = universes[0] if universes else None
        selection = selections[0] if selections else None
        job = self.active_analysis_job()
        return {
            "workspace_id": "default",
            "metadata_universe": None if universe is None else _universe_row(universe),
            "metadata_universes": [_universe_row(item) for item in project_history],
            "univariate_selection": None if selection is None else _selection_row(selection),
            "stages": stages,
            # Small identifier/status history used to keep previous results
            # inspectable without allowing a generic latest-run substitution.
            "history": history,
            "active_job": job,
        }

    def active_analysis_job(self) -> JsonRow | None:
        """Return a small durable job DTO; this is safe for frequent browser polling."""
        for status in ("queued", "running", "failed", "cancelled", "succeeded"):
            jobs = self._state.list_analysis_jobs(status=status, limit=1)
            if jobs:
                return _job_row(jobs[0])
        return None

    def analysis_job_status(self, job_id: str) -> JsonRow:
        return _job_row(self._state.get_analysis_job(job_id))

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
            self._state.update_job_progress(
                job.job_id, current=0, total=None, phase="loading_market_data"
            )
            return self.run_univariate(job.input_ref, job_id=job.job_id)
        if job.stage == "bivariate":
            try:
                result = self.run_bivariate(job.input_ref, job_id=job.job_id)
            except TypeError as error:
                if "unexpected keyword argument 'job_id'" not in str(error):
                    raise
                result = self.run_bivariate(job.input_ref)
            run_id = result.get("run_id")
            if result.get("status") == "succeeded" and isinstance(run_id, str):
                self.start_multivariate_job(
                    selection_id=job.input_ref,
                    bivariate_run_id=run_id,
                    objective="return_risk",
                )
            return result
        if job.stage == "multivariate":
            run = self._state.get_analysis_run(job.input_ref)
            try:
                return self.run_multivariate(
                    selection_id=run.input_ref,
                    bivariate_run_id=run.run_id,
                    objective=job.requested_objective or "return_risk",
                    job_id=job.job_id,
                )
            except TypeError as error:
                if "unexpected keyword argument 'job_id'" not in str(error):
                    raise
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
        if artifact.document.get("storage") == "row_items":
            item_count = artifact.document.get("item_count")
            if not isinstance(item_count, int) or item_count < 0:
                raise ApplicationServiceError("analysis_artifact_invalid")
            rows: list[JsonRow] = []
            for offset in range(0, item_count, 500):
                items = self._state.list_analysis_artifact_items(
                    artifact.artifact_id, offset=offset, limit=min(500, item_count - offset)
                )
                for item in items:
                    document = getattr(item, "document", None)
                    if not isinstance(document, dict):
                        raise ApplicationServiceError("analysis_artifact_invalid")
                    rows.append(cast(JsonRow, document))
            if len(rows) != item_count:
                raise ApplicationServiceError("analysis_artifact_invalid")
            return ComputedRun(
                run_id=run.run_id,
                source_id=run.logical_hash,
                algorithm_version=run.algorithm_version,
                rows=tuple(rows),
            )
        raw_items = artifact.document.get("items")
        if not isinstance(raw_items, list):
            raise ApplicationServiceError("analysis_artifact_invalid")
        inline_rows = tuple(cast(JsonRow, item) for item in raw_items if isinstance(item, dict))
        if len(inline_rows) != len(raw_items):
            raise ApplicationServiceError("analysis_artifact_invalid")
        return ComputedRun(
            run_id=run.run_id,
            source_id=run.logical_hash,
            algorithm_version=run.algorithm_version,
            rows=inline_rows,
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

    def _bivariate_artifact(self, run_id: str) -> AnalysisArtifactRecord:
        """Resolve the current row-backed pair artifact, with legacy read compatibility."""
        try:
            return self._artifact(run_id, "bivariate.rows@v2")
        except ApplicationServiceError:
            return self._artifact(run_id, "bivariate_rows")

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

    def _put_row_backed_artifact(
        self,
        run_id: str,
        artifact_type: str,
        rows: Sequence[JsonRow],
        *,
        summary: Mapping[str, JsonValue],
    ) -> None:
        items = tuple(
            AnalysisArtifactItem(
                item_key=_row_member_id(row), document=cast(dict[str, JsonValue], dict(row))
            )
            for row in rows
        )
        document: JsonRow = {
            "schema": artifact_type,
            "storage": "row_items",
            "item_count": len(items),
            "summary": dict(summary),
        }
        content_hash = stable_hash(
            {
                "document": document,
                "items": [item.document for item in items],
            }
        )
        artifact_id = opaque_id(
            "analysis-artifact",
            {"run_id": run_id, "artifact_type": artifact_type, "content_hash": content_hash},
        )
        self._state.publish_row_backed_analysis_artifact(
            artifact_id=artifact_id,
            run_id=run_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            document=cast(Mapping[str, JsonValue], document),
            items=items,
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
