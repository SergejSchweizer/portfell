from __future__ import annotations

import copy
from datetime import date

from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.hosted_readiness import (
    MANDATORY_DECISIONS,
    failed_results,
    load_readiness,
    local_only_mode_allowed,
    public_hosted_mode_allowed,
    validate_database_readiness,
    validate_readiness,
    validate_runtime_readiness,
)


class FakeDatabaseCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class FakeDatabaseConnection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.closed = False
        self.queries: list[str] = []

    def execute(self, sql: str) -> FakeDatabaseCursor:
        self.queries.append(sql)
        return FakeDatabaseCursor(self.rows)

    def close(self) -> None:
        self.closed = True


def test_readiness_decisions_remain_complete_after_legacy_db_removal() -> None:
    payload = load_readiness()
    decisions = {row["id"] for row in payload["decisions"]}
    assert decisions == set(MANDATORY_DECISIONS)
    assert not failed_results(validate_readiness(payload, today=date(2026, 8, 30)))
    assert public_hosted_mode_allowed(payload, today=date(2026, 8, 30))


def test_readiness_fails_closed_for_incomplete_license() -> None:
    payload = copy.deepcopy(load_readiness())
    payload["decisions"][0]["approved_uses"] = ["cross-customer-storage"]
    failures = failed_results(validate_readiness(payload, today=date(2026, 8, 30)))
    assert any(
        item.name == "decision.shared-data-provider-license.approved_uses" for item in failures
    )
    assert not public_hosted_mode_allowed(payload, today=date(2026, 8, 30))


def test_local_only_mode_is_independent_of_removed_database_authority_selector() -> None:
    payload = load_readiness()
    payload["public_hosted_mode"] = "disabled"
    assert local_only_mode_allowed(payload, today=date(2026, 8, 30))
    assert not failed_results(
        validate_runtime_readiness(
            {"PORTFELL_DATABASE_URL": "postgresql://portfell_app@postgres:5432/portfell_dash"}
        )
    )
    failures = failed_results(
        validate_runtime_readiness({"PORTFELL_DATABASE_URL": "sqlite:///old.db"})
    )
    assert [item.name for item in failures] == ["runtime.database_url_configured"]


def test_database_readiness_reads_only_clean_app_state_catalog() -> None:
    versions = [(migration.version,) for migration in APP_STATE_MIGRATIONS]
    connection = FakeDatabaseConnection(versions)
    failures = failed_results(
        validate_database_readiness(
            "postgresql://portfell_app@postgres:5432/portfell_dash",
            connect=lambda _: connection,
        )
    )
    assert failures == []
    assert connection.closed
    assert connection.queries == ["select version from portfell.schema_migrations order by version"]


def test_database_readiness_rejects_wrong_clean_catalog_head() -> None:
    connection = FakeDatabaseConnection([])
    failures = failed_results(
        validate_database_readiness(
            "postgresql://portfell_app@postgres:5432/portfell_dash",
            connect=lambda _: connection,
        )
    )
    assert [item.name for item in failures] == ["database.catalog_current"]
