from __future__ import annotations

import json

from portfell.hosted_project_settings_repository import PostgresProjectSettingsRepository


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _Connection:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._row = row

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor(self._row if "select settings" in sql else None)


def test_postgres_project_settings_returns_contract_defaults_when_unset() -> None:
    connection = _Connection()

    settings = PostgresProjectSettingsRepository(connection).univariate(
        user_id="user-1", project_id="project-1"
    )

    assert settings == {
        "dividend_frequencies": [],
        "statistic_labels": {},
        "statistic_ranges": {},
    }
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", "user-1"),
    )


def test_postgres_project_settings_persists_normalised_document_under_rls() -> None:
    connection = _Connection()

    saved = PostgresProjectSettingsRepository(connection).save_univariate(
        user_id="user-1",
        project_id="project-1",
        settings={"dividend_frequencies": ["monthly"]},
    )

    assert saved["dividend_frequencies"] == ["monthly"]
    assert saved["statistic_labels"] == {}
    assert connection.calls[0][1] == ("portfell.current_user_id", "user-1")
    statement, parameters = connection.calls[1]
    assert "on conflict (project_id) do update" in statement
    assert parameters[:2] == ("project-1", "user-1")
    assert json.loads(str(parameters[2])) == saved


def test_postgres_project_settings_rejects_non_document_projection() -> None:
    connection = _Connection(([],))

    try:
        PostgresProjectSettingsRepository(connection).univariate(
            user_id="user-1", project_id="project-1"
        )
    except ValueError as error:
        assert str(error) == "project_univariate_settings_projection_invalid"
    else:
        raise AssertionError("invalid database projection must be rejected")
