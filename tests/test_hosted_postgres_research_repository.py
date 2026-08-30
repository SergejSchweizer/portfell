from __future__ import annotations

from portfell.hosted_postgres_research_repository import PostgresResearchRepository
from portfell.hosted_research_workflow import ResearchRun, UnivariateSelection
from portfell.selection_filters import Predicate


class _Cursor:
    def fetchone(self) -> tuple[object, ...] | None:
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        return []


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


class _ResultCursor:
    def __init__(
        self,
        row: tuple[object, ...] | None = None,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._row = row
        self._rows = [] if rows is None else rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _WorkflowConnection(_Connection):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _ResultCursor:
        self.calls.append((sql, parameters))
        if "from portfell_app.research_runs" in sql:
            return _ResultCursor(
                (
                    "univariate-run-1",
                    "00000000-0000-5000-8000-000000000001",
                    "source-1",
                    "complete",
                    3,
                    3,
                    0,
                )
            )
        if "from portfell_app.research_run_rows" in sql:
            return _ResultCursor(
                rows=[
                    (
                        {
                            "isin": "IE00A",
                            "exchange": "XETRA",
                            "code": "AAA",
                            "distribution_frequency": "monthly",
                            "mean": 1.0,
                        },
                    ),
                    (
                        {
                            "isin": "IE00B",
                            "exchange": "XETRA",
                            "code": "BBB",
                            "distribution_frequency": "annual",
                            "mean": 1.0,
                        },
                    ),
                    (
                        {
                            "isin": "IE00C",
                            "exchange": "XETRA",
                            "code": "CCC",
                            "distribution_frequency": "monthly",
                            "mean": 3.0,
                        },
                    ),
                ]
            )
        if "current_univariate_selection_preferences as preference" in sql:
            return _ResultCursor()
        if "from portfell_app.project_univariate_settings" in sql:
            return _ResultCursor(
                (
                    {
                        "dividend_frequencies": ["monthly"],
                        "statistic_ranges": {"mean": [{"minimum": 0.0, "maximum": 2.0}]},
                    },
                )
            )
        if "from portfell_app.univariate_selections" in sql:
            return _ResultCursor()
        if "current_multivariate_run_preferences" in sql:
            return _ResultCursor()
        return _ResultCursor()


class _Projects:
    def list_projects(self, user_id: str) -> tuple[object, ...]:
        del user_id
        return ()


class _Selections:
    def by_id(self, *, selection_id: str, user_id: str) -> None:
        del selection_id, user_id
        return None


class _Analyses:
    def get(self, *, user_id: str, run_id: str) -> None:
        del user_id, run_id
        return None

    def save(self, record: object) -> object:
        return record


def _repository(connection: _Connection) -> PostgresResearchRepository:
    return PostgresResearchRepository(
        connection,
        projects=_Projects(),  # type: ignore[arg-type]
        selections=_Selections(),  # type: ignore[arg-type]
        analyses=_Analyses(),  # type: ignore[arg-type]
    )


def test_postgres_research_repository_binds_each_run_to_its_owned_project() -> None:
    connection = _Connection()
    user_id = "00000000-0000-5000-8000-000000000001"
    project_id = "00000000-0000-5000-8000-000000000002"

    _repository(connection).bind_project_run(
        user_id=user_id, project_id=project_id, run_id="univariate-run-1"
    )

    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", user_id),
    )
    assert "project_research_run_mappings" in connection.calls[1][0]
    assert connection.calls[1][1] == ("univariate-run-1", user_id, project_id)


def test_postgres_research_repository_persists_run_and_rows_under_bound_user() -> None:
    connection = _Connection()
    run = ResearchRun(
        "univariate-run-1",
        "00000000-0000-5000-8000-000000000001",
        "source-1",
        "complete",
        ({"isin": "IE00"},),
        1,
        1,
    )

    _repository(connection).save_univariate_run(run)

    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", run.user_id),
    )
    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "insert into portfell_app.research_runs" in statements
    assert "delete from portfell_app.research_run_rows" in statements
    assert "insert into portfell_app.research_run_rows" in statements
    row_parameters = connection.calls[-1][1]
    assert row_parameters[:3] == (run.run_id, run.user_id, 0)


def test_postgres_research_repository_persists_selection_rows_and_preferences() -> None:
    connection = _Connection()
    selection = UnivariateSelection(
        "univariate-selection-1",
        "00000000-0000-5000-8000-000000000001",
        "univariate-run-1",
        ("IE00:XETRA:AAA",),
        (Predicate("annual_return_pct", ">=", "5.0"),),
        ({"isin": "IE00"},),
        1,
    )
    repository = _repository(connection)

    assert repository.save_univariate_selection(selection) == selection
    repository.set_current_univariate_selection(selection.user_id, selection.selection_id)

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "insert into portfell_app.univariate_selections" in statements
    assert "on conflict (selection_id) do nothing" in statements
    assert "insert into portfell_app.univariate_selection_rows" in statements
    assert "current_univariate_selection_preferences" in statements
    assert all(
        parameters[1] == selection.user_id
        for statement, parameters in connection.calls
        if "research_run_rows" in statement and "insert" in statement
    )


def test_postgres_workflow_reads_a_missing_univariate_selection_without_writing() -> None:
    connection = _WorkflowConnection()

    workflow = _repository(connection).workflow_state(
        user_id="00000000-0000-5000-8000-000000000001",
        project_id="00000000-0000-5000-8000-000000000002",
        metadata_selection_id="metadata-selection-1",
    )

    assert workflow.univariate_run_id == "univariate-run-1"
    assert workflow.univariate_selection_id is None
    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "insert into portfell_app.univariate_selections" not in statements
    assert "insert into portfell_app.current_univariate_selection_preferences" not in statements
