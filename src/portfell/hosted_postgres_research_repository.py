"""PostgreSQL implementation of the hosted research-run repository."""

# ruff: noqa: E501

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from typing import Literal, Protocol, cast

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_analysis_record_repository import AnalysisRecordRepository
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_service_support import opaque_id, stable_hash
from portfell.hosted_api_state import AnalysisRecord, ProjectRecord, SelectionRecord
from portfell.hosted_catalog import set_authenticated_user_sql
from portfell.hosted_postgres_workflow import WorkflowResearchState
from portfell.hosted_quote_lifecycle_repository import QuoteLifecycleRepository
from portfell.hosted_repository_importer import ProjectRepository
from portfell.hosted_research_workflow import (
    ResearchRun,
    RunStatus,
    UnivariateSelection,
    bivariate_source_id,
    create_full_univariate_selection,
)
from portfell.hosted_selection_repository import SelectionRepository, selection_record
from portfell.hosted_univariate_selection_settings import apply_univariate_selection_settings
from portfell.selection_filters import Predicate
from portfell.table_io import JsonRow


class ResearchCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


class ResearchConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> ResearchCursor: ...


QuoteRowsReader = Callable[[str], tuple[JsonRow, ...]]


class PostgresResearchRepository:
    """Persist univariate and bivariate runs without a process-local authority."""

    def __init__(
        self,
        connection: ResearchConnection,
        *,
        projects: ProjectRepository,
        selections: SelectionRepository,
        quotes: QuoteLifecycleRepository,
        quote_rows: QuoteRowsReader,
        analyses: AnalysisRecordRepository,
    ) -> None:
        self._connection = connection
        self._projects = projects
        self._selections = selections
        self._quotes = quotes
        self._quote_rows = quote_rows
        self._analyses = analyses

    def metadata_selection(self, selection_id: str, user_id: str) -> SelectionRecord:
        selection = self._selections.by_id(selection_id=selection_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return selection_record(selection)

    def quote_run(self, run_id: str, user_id: str) -> ProviderDownloadRun:
        run = self._quotes.get(user_id=user_id, run_id=run_id)
        if run is None:
            raise HostedApplicationError(404, "not_found")
        return run

    def quote_rows(self, run_id: str) -> tuple[JsonRow, ...]:
        return self._quote_rows(run_id)

    def univariate_run(self, run_id: str, user_id: str) -> ResearchRun:
        return self._run(run_id=run_id, user_id=user_id, kind="univariate", required=True)

    def find_univariate_run(self, run_id: str, user_id: str) -> ResearchRun | None:
        return self._run(run_id=run_id, user_id=user_id, kind="univariate", required=False)

    def save_univariate_run(self, run: ResearchRun) -> None:
        self._save_run(run, kind="univariate")

    def delete_univariate_run(self, run_id: str) -> None:
        self._connection.execute(
            "delete from portfell_app.research_runs where research_run_id = %s and run_kind = 'univariate'",
            (run_id,),
        )

    def bind_quote_run(self, univariate_run_id: str, quote_run_id: str) -> None:
        self._connection.execute(
            """
insert into portfell_app.research_run_quote_bindings (research_run_id, user_id, quote_run_id)
select research_run_id, user_id, %s::uuid
from portfell_app.research_runs
where research_run_id = %s and run_kind = 'univariate'
on conflict (research_run_id) do update set quote_run_id = excluded.quote_run_id
""",
            (quote_run_id, univariate_run_id),
        )

    def quote_run_id(self, univariate_run_id: str) -> str:
        row = self._connection.execute(
            "select quote_run_id::text from portfell_app.research_run_quote_bindings where research_run_id = %s",
            (univariate_run_id,),
        ).fetchone()
        return "" if row is None or len(row) != 1 or not isinstance(row[0], str) else row[0]

    def univariate_selection(self, selection_id: str, user_id: str) -> UnivariateSelection:
        self._bind(user_id)
        selection = self._selection(selection_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return selection

    def univariate_selections(self, user_id: str) -> tuple[UnivariateSelection, ...]:
        self._bind(user_id)
        rows = self._connection.execute(
            "select selection_id from portfell_app.univariate_selections order by created_at, selection_id"
        ).fetchall()
        return tuple(
            selection
            for row in rows
            if len(row) == 1 and isinstance(row[0], str)
            if (selection := self._selection(row[0])) is not None
        )

    def save_univariate_selection(self, selection: UnivariateSelection) -> UnivariateSelection:
        self._bind(selection.user_id)
        existing = self._selection(selection.selection_id)
        if existing is not None:
            return existing
        self._connection.execute(
            "insert into portfell_app.univariate_selections (selection_id, user_id, source_run_id, member_ids, predicates, input_count) values (%s, %s::uuid, %s, %s::jsonb, %s::jsonb, %s)",
            (
                selection.selection_id,
                selection.user_id,
                selection.source_run_id,
                json.dumps(selection.member_ids),
                json.dumps([_predicate_row(item) for item in selection.predicates]),
                selection.input_count,
            ),
        )
        self._replace_rows(
            "univariate_selection_rows",
            "selection_id",
            selection.selection_id,
            selection.user_id,
            selection.rows,
        )
        return selection

    def set_current_univariate_selection(self, user_id: str, selection_id: str) -> None:
        self._bind(user_id)
        self._connection.execute(
            "insert into portfell_app.current_univariate_selection_preferences (user_id, selection_id) values (%s::uuid, %s) on conflict (user_id) do update set selection_id = excluded.selection_id, updated_at = now()",
            (user_id, selection_id),
        )

    def bivariate_run(self, run_id: str, user_id: str) -> ResearchRun:
        return self._run(run_id=run_id, user_id=user_id, kind="bivariate", required=True)

    def find_bivariate_run(self, run_id: str, user_id: str) -> ResearchRun | None:
        return self._run(run_id=run_id, user_id=user_id, kind="bivariate", required=False)

    def save_bivariate_run(self, run: ResearchRun) -> None:
        self._save_run(run, kind="bivariate")

    def workflow_state(
        self, *, user_id: str, project_id: str, metadata_selection_id: str
    ) -> WorkflowResearchState:
        """Read the current durable research chain for a shared-market project."""

        self._bind(user_id)
        univariate_source = stable_hash(
            {"selection_id": metadata_selection_id, "quote_run_id": "shared-market"}
        )
        univariate_run_id = opaque_id("univariate-run", f"{user_id}:{univariate_source}")
        univariate = self._run_row(univariate_run_id, "univariate")
        if univariate is None:
            return WorkflowResearchState()
        selection = self._current_selection_for_run(user_id, univariate.run_id)
        if univariate.status == "complete":
            selected_rows = apply_univariate_selection_settings(
                univariate.rows, self._univariate_selection_settings(project_id)
            )
            selection = self.save_univariate_selection(
                create_full_univariate_selection(
                    user_id=user_id, run=univariate, rows=selected_rows
                )
            )
            self.set_current_univariate_selection(user_id, selection.selection_id)
        if selection is None:
            return WorkflowResearchState(
                univariate_run_id=univariate.run_id,
                univariate_status=univariate.status,
            )
        bivariate_source = bivariate_source_id(selection)
        bivariate_run_id = opaque_id("bivariate-run", f"{user_id}:{bivariate_source}")
        bivariate = self._run_row(bivariate_run_id, "bivariate")
        multivariate = self._current_multivariate(project_id, bivariate_run_id)
        return WorkflowResearchState(
            univariate_run_id=univariate.run_id,
            univariate_status=univariate.status,
            univariate_selection_id=selection.selection_id,
            univariate_selected_isins=len(
                {member.split(":", 1)[0] for member in selection.member_ids}
            ),
            bivariate_run_id=None if bivariate is None else bivariate.run_id,
            bivariate_status=None if bivariate is None else bivariate.status,
            multivariate_run_id=None if multivariate is None else multivariate[0],
            multivariate_status=None if multivariate is None else multivariate[1],
        )

    def project(self, project_id: str, user_id: str) -> ProjectRecord:
        for project in self._projects.list_projects(user_id):
            if project.project_id == project_id:
                return ProjectRecord(project.project_id, project.user_id, project.name)
        raise HostedApplicationError(404, "not_found")

    def analysis(self, run_id: str, user_id: str) -> AnalysisRecord:
        analysis = self._analyses.get(user_id=user_id, run_id=run_id)
        if analysis is None:
            raise HostedApplicationError(404, "not_found")
        return analysis

    def save_analysis(self, analysis: AnalysisRecord) -> None:
        self._analyses.save(analysis)

    def cached_id(self, user_id: str, operation: str, key: str | None) -> str | None:
        if key is None:
            return None
        self._bind(user_id)
        row = self._connection.execute(
            "select response_ref from portfell_app.request_idempotency where operation = %s and idempotency_key = %s",
            (operation, key),
        ).fetchone()
        return row[0] if row is not None and len(row) == 1 and isinstance(row[0], str) else None

    def remember_id(self, user_id: str, operation: str, key: str | None, row_id: str) -> None:
        if key is None:
            return
        self._bind(user_id)
        self._connection.execute(
            "insert into portfell_app.request_idempotency (user_id, operation, idempotency_key, request_hash, response_ref) values (%s::uuid, %s, %s, %s, %s) on conflict (user_id, operation, idempotency_key) do nothing",
            (user_id, operation, key, operation, row_id),
        )

    def audit(self, user_id: str, action: str) -> None:
        self._bind(user_id)
        self._connection.execute(
            "insert into portfell_app.audit_events (audit_event_id, user_id, event_type, subject_ref, metadata) values (%s::uuid, %s::uuid, %s, %s, '{}'::jsonb)",
            (str(uuid.uuid4()), user_id, action, action),
        )

    def _save_run(self, run: ResearchRun, *, kind: str) -> None:
        self._bind(run.user_id)
        self._connection.execute(
            "insert into portfell_app.research_runs (research_run_id, user_id, run_kind, source_id, status, total, completed, failed) values (%s, %s::uuid, %s, %s, %s, %s, %s, %s) on conflict (research_run_id) do update set status = excluded.status, total = excluded.total, completed = excluded.completed, failed = excluded.failed, updated_at = now()",
            (
                run.run_id,
                run.user_id,
                kind,
                run.source_id,
                run.status,
                run.total,
                run.completed,
                run.failed,
            ),
        )
        self._replace_rows(
            "research_run_rows", "research_run_id", run.run_id, run.user_id, run.rows
        )

    def _run(self, *, run_id: str, user_id: str, kind: str, required: bool) -> ResearchRun:
        self._bind(user_id)
        run = self._run_row(run_id, kind)
        if run is None and required:
            raise HostedApplicationError(404, "not_found")
        return cast(ResearchRun, run)

    def _run_row(self, run_id: str, kind: str) -> ResearchRun | None:
        row = self._connection.execute(
            "select research_run_id, user_id::text, source_id, status, total, completed, failed from portfell_app.research_runs where research_run_id = %s and run_kind = %s",
            (run_id, kind),
        ).fetchone()
        if row is None:
            return None
        if (
            len(row) != 7
            or not all(isinstance(item, str) for item in row[:4])
            or not all(isinstance(item, int) for item in row[4:])
        ):
            raise RuntimeError("research_run_projection_invalid")
        rows = self._rows("research_run_rows", "research_run_id", run_id)
        run_id_value = cast(str, row[0])
        user_id = cast(str, row[1])
        source_id = cast(str, row[2])
        status = cast(RunStatus, row[3])
        total, completed, failed = (cast(int, value) for value in row[4:])
        return ResearchRun(run_id_value, user_id, source_id, status, rows, total, completed, failed)

    def _selection(self, selection_id: str) -> UnivariateSelection | None:
        row = self._connection.execute(
            "select selection_id, user_id::text, source_run_id, member_ids, predicates, input_count from portfell_app.univariate_selections where selection_id = %s",
            (selection_id,),
        ).fetchone()
        if row is None:
            return None
        if (
            len(row) != 6
            or not all(isinstance(item, str) for item in row[:3])
            or not isinstance(row[3], list)
            or not isinstance(row[4], list)
            or not isinstance(row[5], int)
        ):
            raise RuntimeError("univariate_selection_projection_invalid")
        selection_id_value = cast(str, row[0])
        user_id = cast(str, row[1])
        source_run_id = cast(str, row[2])
        member_ids = tuple(cast(list[str], row[3]))
        predicates = tuple(_predicate(value) for value in cast(list[Mapping[str, object]], row[4]))
        input_count = row[5]
        return UnivariateSelection(
            selection_id_value,
            user_id,
            source_run_id,
            member_ids,
            predicates,
            self._rows("univariate_selection_rows", "selection_id", selection_id),
            input_count,
        )

    def _current_selection_for_run(self, user_id: str, run_id: str) -> UnivariateSelection | None:
        row = self._connection.execute(
            """
select preference.selection_id
from portfell_app.current_univariate_selection_preferences as preference
join portfell_app.univariate_selections as selection
  on selection.selection_id = preference.selection_id
where preference.user_id = %s::uuid and selection.source_run_id = %s
""",
            (user_id, run_id),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], str):
            return None
        return self._selection(row[0])

    def _univariate_selection_settings(self, project_id: str) -> JsonRow:
        row = self._connection.execute(
            "select settings from portfell_app.project_univariate_settings where project_id = %s::uuid",
            (project_id,),
        ).fetchone()
        if row is None:
            return {}
        if len(row) != 1 or not isinstance(row[0], dict):
            raise RuntimeError("project_univariate_settings_projection_invalid")
        return cast(JsonRow, row[0])

    def _current_multivariate(
        self, project_id: str, bivariate_run_id: str
    ) -> tuple[str, Literal["ready", "running", "complete", "failed", "stale"]] | None:
        row = self._connection.execute(
            """
select run.multivariate_run_id, run.status
from portfell_app.current_multivariate_run_preferences as preference
join portfell_app.multivariate_runs as run
  on run.multivariate_run_id = preference.multivariate_run_id
where preference.project_id = %s::uuid and run.bivariate_run_id = %s
""",
            (project_id, bivariate_run_id),
        ).fetchone()
        if (
            row is None
            or len(row) != 2
            or not isinstance(row[0], str)
            or row[1] not in {"ready", "running", "complete", "failed", "stale"}
        ):
            return None
        return row[0], cast(Literal["ready", "running", "complete", "failed", "stale"], row[1])

    def _replace_rows(
        self, table: str, id_column: str, row_id: str, user_id: str, rows: tuple[JsonRow, ...]
    ) -> None:
        self._connection.execute(
            f"delete from portfell_app.{table} where {id_column} = %s", (row_id,)
        )
        for ordinal, row in enumerate(rows):
            self._connection.execute(
                f"insert into portfell_app.{table} ({id_column}, user_id, ordinal, row_data) values (%s, %s::uuid, %s, %s::jsonb)",
                (row_id, user_id, ordinal, json.dumps(row, sort_keys=True, separators=(",", ":"))),
            )

    def _rows(self, table: str, id_column: str, row_id: str) -> tuple[JsonRow, ...]:
        return tuple(
            dict(cast(Mapping[str, object], row[0]))
            for row in self._connection.execute(
                f"select row_data from portfell_app.{table} where {id_column} = %s order by ordinal",
                (row_id,),
            ).fetchall()
            if len(row) == 1 and isinstance(row[0], Mapping)
        )

    def _bind(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _predicate_row(predicate: Predicate) -> JsonRow:
    return {"metric": predicate.field, "operator": predicate.operator, "value": predicate.expected}


def _predicate(value: Mapping[str, object]) -> Predicate:
    metric, operator, expected = value.get("metric"), value.get("operator"), value.get("value")
    if (
        not isinstance(metric, str)
        or not isinstance(operator, str)
        or not isinstance(expected, str)
    ):
        raise RuntimeError("univariate_selection_projection_invalid")
    return Predicate(metric, operator, expected)
