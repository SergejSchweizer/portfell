"""Readiness gates for the clean single-workspace PostgreSQL runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol, cast

from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.hosted_data_planes import REQUIRED_SHARED_DATA_LICENSE_USES
from portfell.hosted_database_connection import connect as connect_database

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
READINESS_PATH = REPOSITORY_ROOT / "docs" / "security" / "hosted_readiness.json"
MANDATORY_DECISIONS: tuple[str, ...] = (
    "shared-data-provider-license",
    "retention-and-account-deletion",
    "gdpr-rights-and-country-coverage",
    "audit-retention-and-incident-response",
    "encrypted-backups-and-restore-drills",
    "kek-recovery-and-rotation",
    "database-role-review",
    "no-automatic-broker-execution",
)


@dataclass(frozen=True)
class ReadinessResult:
    name: str
    passed: bool
    message: str


def load_readiness(path: Path = READINESS_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as readiness_file:
        payload = cast(object, json.load(readiness_file))
    if not isinstance(payload, dict):
        raise ValueError("hosted readiness must be a JSON object")
    return cast(dict[str, Any], payload)


def failed_results(results: Iterable[ReadinessResult]) -> list[ReadinessResult]:
    return [result for result in results if not result.passed]


def _decision_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("decisions", [])
    if not isinstance(raw, list):
        raise ValueError("decisions must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in cast(list[object], raw):
        if not isinstance(item, dict):
            raise ValueError("decision rows must be objects")
        decision = cast(dict[str, Any], item)
        identifier = decision.get("id")
        if not isinstance(identifier, str):
            raise ValueError("decision id must be a string")
        result[identifier] = decision
    return result


def _iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_readiness(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> list[ReadinessResult]:
    """Validate operator/security decisions without coupling to the retired DB catalog."""
    resolved = payload or load_readiness()
    resolved_today = today or date.today()
    decisions = _decision_map(resolved)
    results: list[ReadinessResult] = []
    for identifier in MANDATORY_DECISIONS:
        decision = decisions.get(identifier)
        if decision is None:
            results.append(
                ReadinessResult(
                    f"decision.{identifier}.present", False, "mandatory decision is missing"
                )
            )
            continue
        owner = decision.get("owner")
        evidence = decision.get("evidence")
        expires = _iso_date(decision.get("expires_on"))
        results.extend(
            (
                ReadinessResult(
                    f"decision.{identifier}.approved",
                    decision.get("status") == "approved",
                    "mandatory decision must be approved",
                ),
                ReadinessResult(
                    f"decision.{identifier}.owner",
                    isinstance(owner, str) and bool(owner),
                    "mandatory decision must have an owner",
                ),
                ReadinessResult(
                    f"decision.{identifier}.evidence",
                    isinstance(evidence, str) and bool(evidence),
                    "mandatory decision must link evidence",
                ),
                ReadinessResult(
                    f"decision.{identifier}.reviewed_on",
                    _iso_date(decision.get("reviewed_on")) is not None,
                    "mandatory decision must have an ISO reviewed_on date",
                ),
                ReadinessResult(
                    f"decision.{identifier}.not_expired",
                    expires is not None and expires >= resolved_today,
                    "mandatory decision must not be expired",
                ),
            )
        )
        if identifier == "shared-data-provider-license":
            approved = decision.get("approved_uses")
            approved_set = {
                value
                for value in cast(list[object], approved)
                if isinstance(value, str)
            } if isinstance(approved, list) else set()
            results.append(
                ReadinessResult(
                    "decision.shared-data-provider-license.approved_uses",
                    set(REQUIRED_SHARED_DATA_LICENSE_USES).issubset(approved_set),
                    "shared-data license must explicitly approve every required use",
                )
            )
    return results


def public_hosted_mode_allowed(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> bool:
    resolved = payload or load_readiness()
    return resolved.get("public_hosted_mode") == "enabled" and not failed_results(
        validate_readiness(resolved, today=today)
    )


def local_only_mode_allowed(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> bool:
    resolved = payload or load_readiness()
    if resolved.get("public_hosted_mode") != "disabled":
        return False
    failures = failed_results(validate_readiness(resolved, today=today))
    return all(result.name.startswith("decision.shared-data-provider-license.") for result in failures)


def _postgres_database_url(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(("postgres://", "postgresql://"))


def validate_runtime_readiness(
    environment: Mapping[str, str] | None = None,
) -> list[ReadinessResult]:
    """Require the clean app database URL; no legacy authority selector exists."""
    resolved = environment if environment is not None else os.environ
    return [
        ReadinessResult(
            "runtime.database_url_configured",
            _postgres_database_url(resolved.get("PORTFELL_DATABASE_URL")),
            "clean Portfell PostgreSQL database URL is required",
        )
    ]


class DatabaseCursor(Protocol):
    def fetchall(self) -> list[Sequence[object]]: ...


class DatabaseConnection(Protocol):
    def execute(self, sql: str) -> DatabaseCursor: ...
    def close(self) -> None: ...


DatabaseConnector = Callable[[str], DatabaseConnection]


def _connect_database(database_url: str) -> DatabaseConnection:
    return cast(DatabaseConnection, connect_database(database_url, autocommit=True))


def validate_database_readiness(
    database_url: str | None = None,
    *,
    connect: DatabaseConnector | None = None,
) -> list[ReadinessResult]:
    """Probe only the clean ``portfell.schema_migrations`` catalog."""
    resolved_url = database_url or os.environ.get("PORTFELL_DATABASE_URL")
    if not _postgres_database_url(resolved_url):
        return _database_unavailable_results()
    assert resolved_url is not None
    try:
        connection = (connect or _connect_database)(resolved_url)
        try:
            rows = connection.execute(
                "select version from portfell.schema_migrations order by version"
            ).fetchall()
        finally:
            connection.close()
    except Exception:
        return _database_unavailable_results()
    versions = tuple(int(row[0]) for row in rows)
    expected = tuple(migration.version for migration in APP_STATE_MIGRATIONS)
    return [
        ReadinessResult(
            "database.connection_available", True, "clean PostgreSQL database is reachable"
        ),
        ReadinessResult(
            "database.catalog_current", versions == expected, "app-state migrations are incomplete"
        ),
    ]


def _database_unavailable_results() -> list[ReadinessResult]:
    return [
        ReadinessResult(
            "database.connection_available", False, "clean PostgreSQL database is unavailable"
        ),
        ReadinessResult(
            "database.catalog_current", False, "app-state migrations are incomplete"
        ),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Portfell runtime readiness.")
    parser.add_argument("--require-database", action="store_true")
    parser.add_argument("--require-runtime", action="store_true")
    args = parser.parse_args(argv)
    if args.require_database:
        results = validate_database_readiness()
    elif args.require_runtime:
        results = validate_runtime_readiness()
    else:
        results = validate_readiness()
    failures = failed_results(results)
    for failure in failures:
        print(f"{failure.name}: {failure.message}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
