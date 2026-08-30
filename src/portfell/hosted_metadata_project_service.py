"""Metadata and metadata-builder project application service."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import (
    metadata_fetch_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    opaque_id,
    stable_hash,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_metadata_repository import MetadataLifecycleRepository, MetadataRun
from portfell.hosted_repository_importer import (
    ProjectRepository,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_selection_repository import SelectionRepository
from portfell.market_source.contracts import Listing
from portfell.market_source.gateway import MarketDataGateway
from portfell.market_source.snapshot import build_market_source_snapshot
from portfell.selection_filters import Predicate, filter_rows, parse_predicates
from portfell.table_io import JsonRow


@dataclass(frozen=True)
class MetadataSourceCatalog:
    """Active source listings and their deterministic external-market lineage."""

    rows: tuple[JsonRow, ...]
    snapshot_id: str


def metadata_source_catalog(gateway: MarketDataGateway) -> MetadataSourceCatalog:
    """Read only active full-identity listings from the external market authority."""
    listings = gateway.read_active_listings()
    snapshot = build_market_source_snapshot(listings=listings, quotes=(), dividends=(), splits=())
    return MetadataSourceCatalog(
        rows=tuple(_listing_row(listing) for listing in listings),
        snapshot_id=snapshot.snapshot_id,
    )


class MetadataProjectService:
    """Own metadata refresh and metadata-derived project transitions."""

    def __init__(
        self,
        state: HostedApiState,
        runtime: HostedRuntimePort,
        project_repository: ProjectRepository,
        selection_repository: SelectionRepository,
        metadata_repository: MetadataLifecycleRepository,
        audit_repository: AuditEventRepository,
        navigation_refresher: Callable[[str], None] | None = None,
        market_catalog: Callable[[], MetadataSourceCatalog] | None = None,
    ) -> None:
        self.state = state
        self.runtime = runtime
        self._projects = project_repository
        self._selections = selection_repository
        self._metadata = metadata_repository
        self._audit_events = audit_repository
        self._navigation_refresher = navigation_refresher
        self._market_catalog = market_catalog

    def _all_isins_rows(self) -> tuple[JsonRow, ...]:
        if self._market_catalog is not None:
            return self._market_catalog().rows
        return self.state.all_isins_rows or self.runtime.all_isins_rows()

    def options(self, user_id: str) -> JsonRow:
        values_by_field: dict[str, dict[str, set[str]]] = {
            field: {} for field in ("exchange", "instrument_type", "country", "currency")
        }
        for row in self._all_isins_rows():
            isin = str(row.get("isin", "")).strip()
            if not isin:
                continue
            for field, values in values_by_field.items():
                value = str(row.get(field, "")).strip()
                if value:
                    values.setdefault(value, set()).add(isin)
        return {
            "metadata_ready": self._market_catalog is not None
            or self._metadata.revision(user_id=user_id) is not None,
            **{
                field: [
                    {"value": value, "isin_count": len(isins)}
                    for value, isins in sorted(values.items())
                ]
                for field, values in values_by_field.items()
            },
        }

    def start_metadata_fetch(self, user_id: str) -> tuple[JsonRow, Callable[[], None]]:
        if self._market_catalog is not None:
            catalog = self._market_catalog()
            run_id = opaque_id("metadata-run", f"{user_id}:{catalog.snapshot_id}")
            run = self._metadata.create(
                MetadataRun(
                    run_id,
                    user_id,
                    "succeeded",
                    len(catalog.rows),
                    len(catalog.rows),
                    0,
                    100,
                    {
                        "row_count": len(catalog.rows),
                        "exchange_count": len({str(row["exchange"]) for row in catalog.rows}),
                        "requested_exchange_count": 0,
                        "skipped_exchanges": [],
                        "snapshot_id": catalog.snapshot_id,
                    },
                )
            )
            self._metadata.set_revision(user_id=user_id, revision_id=catalog.snapshot_id)
            self._audit(user_id, "fetch_all_metadata.completed")
            return metadata_fetch_row(_metadata_row(run)), lambda: None
        raise HostedApplicationError(503, "market_source_not_configured")

    def metadata_fetch_status(self, user_id: str, run_id: str) -> JsonRow:
        run = self._metadata.status(user_id=user_id, run_id=run_id)
        if run is None:
            raise HostedApplicationError(404, "metadata_run_not_found")
        return metadata_fetch_row(_metadata_row(run))

    def create_project_from_criteria(
        self,
        user_id: str,
        *,
        exchange: str,
        name: str,
        instrument_type: str,
        country: str,
        currency: str,
        idempotency_key: str | None,
    ) -> JsonRow:
        catalog = self._market_catalog() if self._market_catalog is not None else None
        if catalog is None and self._metadata.revision(user_id=user_id) is None:
            raise HostedApplicationError(422, "metadata_required")
        values = (
            ("exchange", "=", exchange),
            ("name", "~", name),
            ("instrument_type", "=", instrument_type),
            ("country", "=", country),
            ("currency", "=", currency),
        )
        predicates = tuple(
            Predicate(field, operator, value.strip())
            for field, operator, value in values
            if value.strip()
        )
        if not predicates:
            raise HostedApplicationError(422, "metadata_builder_required")
        selected_rows = _ordered_listings(
            filter_rows(catalog.rows if catalog is not None else self._all_isins_rows(), predicates)
        )
        if not selected_rows:
            raise HostedApplicationError(422, "metadata_builder_empty")
        project_name = (
            "_".join(
                part
                for part in ("_".join(value.strip().casefold().split()) for _, _, value in values)
                if part
            )
            or "metadata_builder_project"
        )
        operation = f"metadata-builder-project:{project_name}"
        request_hash = stable_hash({"operation": operation, "members": selected_rows})
        cached = (
            self._metadata.idempotent_response(
                user_id=user_id, operation=operation, key=idempotency_key, request_hash=request_hash
            )
            if idempotency_key is not None
            else None
        )
        if cached is not None:
            project = self._project(user_id, cached)
            selection = self._selection_for_project(user_id, project.project_id)
            self._projects.set_current_project(user_id=user_id, project_id=project.project_id)
            self._refresh_navigation(user_id)
            return self._project_selection_row(project, selection)
        project_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:project:{user_id}:{project_name}")
        )
        try:
            existing_project = self._project(user_id, project_id)
        except HostedApplicationError as error:
            if error.status_code != 404 or error.code != "not_found":
                raise
            existing_project = None
        if existing_project is not None:
            selection = self._selection_for_project(user_id, project_id)
            self._projects.set_current_project(user_id=user_id, project_id=project_id)
            self._refresh_navigation(user_id)
            return self._project_selection_row(existing_project, selection)
        project = self._record(
            self._projects.create_project(TenantProject(project_id, user_id, project_name))
        )
        members = tuple(f"{row['isin']}:{row['exchange']}:{row['code']}" for row in selected_rows)
        selection_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"portfell:selection:{user_id}:{project_id}:{project_name}:{members}",
            )
        )
        selection = self._selection_record(
            self._selections.create(
                TenantSelection(
                    selection_id,
                    project_id,
                    user_id,
                    project_name,
                    members,
                    tuple(predicate.as_text() for predicate in predicates),
                )
            )
        )
        self._projects.set_current_project(user_id=user_id, project_id=project_id)
        if catalog is not None:
            self._metadata.set_revision(user_id=user_id, revision_id=catalog.snapshot_id)
        self.runtime.write_metadata_selection(selection_id, selected_rows, predicates)
        if idempotency_key is not None:
            self._metadata.remember_idempotency(
                user_id=user_id,
                operation=operation,
                key=idempotency_key,
                request_hash=request_hash,
                response_ref=project_id,
            )
        self._audit(user_id, "metadata_builder.project.create")
        self._refresh_navigation(user_id)
        return self._project_selection_row(project, selection)

    def _refresh_navigation(self, user_id: str) -> None:
        if self._navigation_refresher is not None:
            self._navigation_refresher(user_id)

    @staticmethod
    def _project_selection_row(project: ProjectRecord, selection: SelectionRecord) -> JsonRow:
        return {
            "project": project_row(project),
            "selection": selection_row(selection),
            "selected_count": _unique_isin_count(selection.member_ids),
        }

    def project_criteria_row(self, project: ProjectRecord, selection: SelectionRecord) -> JsonRow:
        fields: JsonRow = {
            "exchange": "",
            "instrument_type": "",
            "country": "",
            "currency": "",
            "name": "",
        }
        try:
            predicates = parse_predicates(list(selection.metadata_builder_predicates))
        except ValueError as error:
            raise HostedApplicationError(500, "metadata_builder_manifest_invalid") from error
        for predicate in predicates:
            if predicate.field == "name" and predicate.operator == "~":
                fields["name"] = predicate.expected
            elif predicate.field in fields and predicate.operator == "=":
                fields[predicate.field] = predicate.expected
        return {
            "project_id": project.project_id,
            "selection_id": selection.selection_id,
            "selected_count": _unique_isin_count(selection.member_ids),
            **fields,
        }

    @staticmethod
    def _record(project: TenantProject) -> ProjectRecord:
        return ProjectRecord(project.project_id, project.user_id, project.name)

    def _project(self, user_id: str, project_id: str) -> ProjectRecord:
        for project in self._projects.list_projects(user_id):
            if project.project_id == project_id:
                return self._record(project)
        raise HostedApplicationError(404, "not_found")

    @staticmethod
    def _selection_record(selection: TenantSelection) -> SelectionRecord:
        return SelectionRecord(
            selection.selection_id,
            selection.user_id,
            selection.project_id,
            selection.name,
            selection.member_ids,
            selection.metadata_builder_predicates,
        )

    def _selection_for_project(self, user_id: str, project_id: str) -> SelectionRecord:
        selection = self._selections.for_project(project_id=project_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return self._selection_record(selection)

    def _audit(self, user_id: str, event_type: str) -> None:
        self._audit_events.append(
            HostedAuditEvent(
                audit_event_id=str(uuid.uuid4()),
                user_id=user_id,
                event_type=event_type,
                subject_ref=f"user:{user_id}",
                metadata={},
            )
        )


def _metadata_row(run: MetadataRun) -> JsonRow:
    return {
        "metadata_run_id": run.metadata_run_id,
        "user_id": run.user_id,
        "status": run.status,
        "total": run.total,
        "completed": run.completed,
        "skipped_exchange_count": run.skipped_exchange_count,
        "percent": run.percent,
        **run.summary,
    }


def _ordered_listings(rows: list[JsonRow]) -> list[JsonRow]:
    """Keep every valid full listing identity in deterministic source order."""

    identities: dict[tuple[str, str, str], JsonRow] = {}
    for row in sorted(
        rows,
        key=lambda value: (
            str(value.get("isin", "")),
            str(value.get("exchange", "")),
            str(value.get("code", "")),
        ),
    ):
        isin = str(row.get("isin", "")).strip()
        exchange = str(row.get("exchange", "")).strip()
        code = str(row.get("code", "")).strip()
        if isin and exchange and code:
            identities.setdefault((isin, exchange, code), row)
    return list(identities.values())


def _listing_row(listing: Listing) -> JsonRow:
    return {
        "isin": listing.key.isin,
        "exchange": listing.key.exchange,
        "code": listing.key.code,
        "name": listing.name,
        "instrument_type": listing.instrument_type,
        "country": listing.country or "",
        "currency": listing.currency or "",
    }


def _unique_isin_count(member_ids: tuple[str, ...]) -> int:
    """Count selected instruments independently of exchange/code aliases."""

    return len({member_id.split(":", 1)[0] for member_id in member_ids if member_id})
