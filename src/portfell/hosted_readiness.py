"""Hosted readiness decision gates for public Portfell deployment."""

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

from portfell.hosted_catalog import migration_plan
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
    """Result for one hosted readiness decision or invariant."""

    name: str
    passed: bool
    message: str


def load_readiness(path: Path = READINESS_PATH) -> dict[str, Any]:
    """Load hosted readiness evidence records."""

    with path.open(encoding="utf-8") as readiness_file:
        payload = cast(object, json.load(readiness_file))
    if not isinstance(payload, dict):
        raise ValueError("hosted readiness must be a JSON object")
    return cast(dict[str, Any], payload)


def validate_readiness(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> list[ReadinessResult]:
    """Validate public-hosted readiness records without mutating production state."""

    resolved = payload or load_readiness()
    resolved_today = today or date.today()
    results: list[ReadinessResult] = []
    decisions = _decision_map(resolved)
    for decision_id in MANDATORY_DECISIONS:
        decision = decisions.get(decision_id)
        results.extend(_validate_decision(decision_id, decision, today=resolved_today))
    results.extend(_validate_mode(resolved, decisions))
    return results


def public_hosted_mode_allowed(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> bool:
    """Return whether public-hosted mode can be enabled."""

    return not failed_results(validate_readiness(payload, today=today))


def local_only_mode_allowed(
    payload: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> bool:
    """Return whether local-only mode is safe while D017 licensing is pending."""

    resolved = payload or load_readiness()
    if resolved.get("public_hosted_mode") != "disabled":
        return False
    allowed_pending = {
        "decision.shared-data-provider-license.approved",
        "decision.shared-data-provider-license.approved_uses",
    }
    return not [
        result
        for result in failed_results(validate_readiness(resolved, today=today))
        if result.name not in allowed_pending
    ]


def failed_results(results: Iterable[ReadinessResult]) -> list[ReadinessResult]:
    """Return failed readiness results in deterministic order."""

    return [result for result in results if not result.passed]


def validate_runtime_readiness(
    environment: Mapping[str, str] | None = None,
) -> list[ReadinessResult]:
    """Verify deployment-only worker secrets exist and are nonempty before cutover."""

    resolved = environment if environment is not None else os.environ
    authority = resolved.get("PORTFELL_HOSTED_AUTHORITY", "local")
    return [
        _secret_file_result(
            "runtime.external_kek_available",
            resolved.get("PORTFELL_EODHD_KEK_FILE"),
            "external KEK secret file is required",
        ),
        _secret_file_result(
            "runtime.operations_credential_available",
            resolved.get("PORTFELL_OPERATIONS_EODHD_TOKEN_FILE"),
            "operations market-data credential file is required",
        ),
        ReadinessResult(
            name="runtime.database_url_configured",
            passed=_postgres_database_url(resolved.get("PORTFELL_DATABASE_URL")),
            message="PostgreSQL database URL is required",
        ),
        ReadinessResult(
            name="runtime.authority_allowed",
            passed=(
                authority == "local" or (authority == "postgres" and public_hosted_mode_allowed())
            ),
            message="PostgreSQL authority requires approved public-hosted readiness",
        ),
    ]


class DatabaseCursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


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
    """Probe an explicit database without exposing connection details."""

    resolved_url = database_url or os.environ.get("PORTFELL_DATABASE_URL")
    if not _postgres_database_url(resolved_url):
        return _database_unavailable_results()
    assert resolved_url is not None
    try:
        connection = (connect or _connect_database)(resolved_url)
        try:
            rows = connection.execute(
                "select version from portfell_private.schema_migrations order by version"
            ).fetchall()
        finally:
            connection.close()
    except Exception:
        return _database_unavailable_results()
    versions = tuple(row[0] for row in rows)
    expected_versions = tuple(migration.version for migration in migration_plan())
    return [
        ReadinessResult("database.connection_available", True, "PostgreSQL database is reachable"),
        ReadinessResult(
            "database.catalog_current",
            versions == expected_versions,
            "hosted catalog migrations are incomplete",
        ),
    ]


def _database_unavailable_results() -> list[ReadinessResult]:
    return [
        ReadinessResult(
            "database.connection_available", False, "PostgreSQL database is unavailable"
        ),
        ReadinessResult(
            "database.catalog_current", False, "hosted catalog migrations are incomplete"
        ),
    ]


def _secret_file_result(name: str, value: str | None, message: str) -> ReadinessResult:
    path = Path(value) if value else None
    available = bool(
        path is not None and path.is_file() and path.read_text(encoding="utf-8").strip()
    )
    return ReadinessResult(name=name, passed=available, message=message)


def _postgres_database_url(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(("postgres://", "postgresql://"))


def _decision_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_decisions = cast(object, payload.get("decisions", []))
    if not isinstance(raw_decisions, list):
        raise ValueError("decisions must be a list")
    decisions: dict[str, dict[str, Any]] = {}
    for raw_decision in cast(list[object], raw_decisions):
        if not isinstance(raw_decision, dict):
            raise ValueError("decision rows must be objects")
        decision = cast(dict[str, Any], raw_decision)
        decision_id = decision.get("id")
        if not isinstance(decision_id, str):
            raise ValueError("decision id must be a string")
        decisions[decision_id] = decision
    return decisions


def _validate_decision(
    decision_id: str,
    decision: dict[str, Any] | None,
    *,
    today: date,
) -> list[ReadinessResult]:
    if decision is None:
        return [
            ReadinessResult(
                name=f"decision.{decision_id}.present",
                passed=False,
                message="mandatory decision is missing",
            )
        ]
    status = decision.get("status")
    reviewed_on = decision.get("reviewed_on")
    expires_on = decision.get("expires_on")
    evidence = decision.get("evidence")
    owner = decision.get("owner")
    results = [
        ReadinessResult(
            name=f"decision.{decision_id}.approved",
            passed=status == "approved",
            message="mandatory decision must be approved",
        ),
        ReadinessResult(
            name=f"decision.{decision_id}.owner",
            passed=isinstance(owner, str) and bool(owner),
            message="mandatory decision must have an owner",
        ),
        ReadinessResult(
            name=f"decision.{decision_id}.evidence",
            passed=isinstance(evidence, str) and bool(evidence),
            message="mandatory decision must link evidence",
        ),
        ReadinessResult(
            name=f"decision.{decision_id}.reviewed_on",
            passed=_is_iso_date(reviewed_on),
            message="mandatory decision must have an ISO reviewed_on date",
        ),
        ReadinessResult(
            name=f"decision.{decision_id}.not_expired",
            passed=_is_future_or_today(expires_on, today=today),
            message="mandatory decision must not be expired",
        ),
    ]
    if decision_id == "shared-data-provider-license":
        approved_uses = decision.get("approved_uses")
        raw_approved_uses = (
            cast(list[object], approved_uses) if isinstance(approved_uses, list) else []
        )
        approved_use_values = [value for value in raw_approved_uses if isinstance(value, str)]
        results.append(
            ReadinessResult(
                name=f"decision.{decision_id}.approved_uses",
                passed=(
                    isinstance(approved_uses, list)
                    and len(approved_use_values) == len(raw_approved_uses)
                    and set(approved_use_values) == set(REQUIRED_SHARED_DATA_LICENSE_USES)
                ),
                message=(
                    "provider license must approve cross-customer storage, derived reuse, "
                    "retention, and service-credential ingestion"
                ),
            )
        )
    return results


def _validate_mode(
    payload: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
) -> list[ReadinessResult]:
    public_hosted_enabled = payload.get("public_hosted_mode") == "enabled"
    approved = all(
        decisions.get(decision_id, {}).get("status") == "approved"
        for decision_id in MANDATORY_DECISIONS
    )
    local_mode = payload.get("local_only_mode") == "available"
    backup_contract = payload.get("backup_contract")
    key_contract = payload.get("key_contract")
    return [
        ReadinessResult(
            name="mode.local_only_available",
            passed=local_mode,
            message="local-only mode must remain available while hosted readiness is blocked",
        ),
        ReadinessResult(
            name="mode.public_enabled_only_when_approved",
            passed=not public_hosted_enabled or approved,
            message=(
                "public-hosted mode cannot be enabled until every mandatory decision is approved"
            ),
        ),
        ReadinessResult(
            name="backup.encrypted_and_separate",
            passed=backup_contract == "encrypted-separate-from-kek",
            message=(
                "database/shared-store backups must be encrypted and stored separately "
                "from KEK recovery material"
            ),
        ),
        ReadinessResult(
            name="keys.restore_fails_closed",
            passed=key_contract == "restore-requires-kek-version",
            message="restore procedures must fail closed without the required KEK version",
        ),
    ]


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_future_or_today(value: object, *, today: date) -> bool:
    if not _is_iso_date(value):
        return False
    return date.fromisoformat(cast(str, value)) >= today


def build_parser() -> argparse.ArgumentParser:
    """Build the hosted readiness CLI parser."""

    parser = argparse.ArgumentParser(description="Validate hosted deployment readiness.")
    parser.add_argument(
        "--require-public-hosted",
        action="store_true",
        help="Fail unless public-hosted mode is fully approved.",
    )
    parser.add_argument(
        "--require-runtime",
        action="store_true",
        help="Fail unless deployment secret files and runtime authority are ready.",
    )
    parser.add_argument(
        "--require-database",
        action="store_true",
        help="Fail unless PostgreSQL is reachable and catalog migrations are current.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run hosted readiness checks."""

    args = build_parser().parse_args(argv)
    results = validate_readiness()
    readiness_failures = failed_results(results)
    runtime_failures = failed_results(validate_runtime_readiness()) if args.require_runtime else []
    database_failures = (
        failed_results(validate_database_readiness()) if args.require_database else []
    )
    failures: list[ReadinessResult] = []
    if args.require_public_hosted:
        failures.extend(readiness_failures)
    if args.require_runtime:
        failures.extend(runtime_failures)
    if args.require_database:
        failures.extend(database_failures)
    if failures:
        for failure in failures:
            print(f"{failure.name}: {failure.message}", file=sys.stderr)
        return 1
    if readiness_failures:
        print("public-hosted mode is blocked; local-only mode remains available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
