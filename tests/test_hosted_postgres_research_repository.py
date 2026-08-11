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


class _Projects:
    def list_projects(self, user_id: str) -> tuple[object, ...]:
        del user_id
        return ()


class _Selections:
    def by_id(self, *, selection_id: str, user_id: str) -> None:
        del selection_id, user_id
        return None


class _Quotes:
    def get(self, *, user_id: str, run_id: str) -> None:
        del user_id, run_id
        return None


def _repository(connection: _Connection) -> PostgresResearchRepository:
    return PostgresResearchRepository(
        connection,
        projects=_Projects(),  # type: ignore[arg-type]
        selections=_Selections(),  # type: ignore[arg-type]
        quotes=_Quotes(),  # type: ignore[arg-type]
        quote_rows=lambda _: (),
    )


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
    assert "insert into portfell_app.univariate_selection_rows" in statements
    assert "current_univariate_selection_preferences" in statements
    assert all(
        parameters[1] == selection.user_id
        for statement, parameters in connection.calls
        if "research_run_rows" in statement and "insert" in statement
    )


def test_postgres_research_repository_binds_quote_reference_to_run_owner() -> None:
    connection = _Connection()

    _repository(connection).bind_quote_run(
        "univariate-run-1", "00000000-0000-5000-8000-000000000010"
    )

    statement, parameters = connection.calls[0]
    assert "select research_run_id, user_id" in statement
    assert "research_run_quote_bindings" in statement
    assert parameters == ("00000000-0000-5000-8000-000000000010", "univariate-run-1")
