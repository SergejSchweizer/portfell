from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from portfell.hosted_readiness import (
    MANDATORY_DECISIONS,
    failed_results,
    load_readiness,
    local_only_mode_allowed,
    main,
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

    def execute(self, _: str) -> FakeDatabaseCursor:
        return FakeDatabaseCursor(self.rows)

    def close(self) -> None:
        self.closed = True


def test_hosted_readiness_records_cover_every_mandatory_decision() -> None:
    payload = load_readiness()
    decisions = {row["id"] for row in payload["decisions"]}

    assert decisions == set(MANDATORY_DECISIONS)
    failures = failed_results(validate_readiness(payload, today=date(2026, 8, 10)))

    assert not failures
    assert not local_only_mode_allowed(payload, today=date(2026, 8, 10))
    assert public_hosted_mode_allowed(payload, today=date(2026, 8, 10))


def test_public_hosted_mode_fails_closed_when_a_decision_is_missing() -> None:
    payload = load_readiness()
    payload["decisions"] = payload["decisions"][:-1]

    failures = failed_results(validate_readiness(payload, today=date(2026, 7, 19)))

    assert failures
    assert not public_hosted_mode_allowed(payload, today=date(2026, 7, 19))


def test_public_hosted_mode_fails_closed_for_expired_review() -> None:
    payload = load_readiness()
    payload["public_hosted_mode"] = "enabled"
    payload["decisions"][0]["expires_on"] = "2026-07-18"

    failures = failed_results(validate_readiness(payload, today=date(2026, 7, 19)))

    assert any(failure.name.endswith(".not_expired") for failure in failures)
    assert not public_hosted_mode_allowed(payload, today=date(2026, 7, 19))


def test_public_hosted_mode_requires_complete_shared_data_license_approval() -> None:
    payload = copy.deepcopy(load_readiness())
    payload["public_hosted_mode"] = "enabled"
    payload["decisions"].append(
        {
            "id": "shared-data-provider-license",
            "status": "approved",
            "owner": "maintainer",
            "reviewed_on": "2026-08-10",
            "expires_on": "2027-08-10",
            "evidence": "docs/security/hosted_readiness.md#d017-provider-license",
            "approved_uses": ["cross-customer-storage"],
        }
    )

    failures = failed_results(validate_readiness(payload, today=date(2026, 8, 10)))

    assert any(
        failure.name == "decision.shared-data-provider-license.approved_uses"
        for failure in failures
    )
    assert not public_hosted_mode_allowed(payload, today=date(2026, 8, 10))


def test_local_only_mode_can_remain_available_while_public_mode_is_disabled() -> None:
    payload = load_readiness()
    payload["public_hosted_mode"] = "disabled"

    assert payload["local_only_mode"] == "available"
    assert local_only_mode_allowed(payload, today=date(2026, 8, 10))


def test_runtime_readiness_fails_closed_for_missing_worker_secret_files(tmp_path: Path) -> None:
    environment = {
        "PORTFELL_EODHD_KEK_FILE": str(tmp_path / "missing-kek"),
        "PORTFELL_OPERATIONS_EODHD_TOKEN_FILE": str(tmp_path / "missing-token"),
    }

    failures = failed_results(validate_runtime_readiness(environment))

    assert {failure.name for failure in failures} == {
        "runtime.external_kek_available",
        "runtime.operations_credential_available",
        "runtime.database_url_configured",
    }


def test_runtime_readiness_accepts_nonempty_worker_secret_files(tmp_path: Path) -> None:
    kek = tmp_path / "kek"
    token = tmp_path / "operations-token"
    kek.write_text("kek-material", encoding="utf-8")
    token.write_text("operations-token", encoding="utf-8")

    assert not failed_results(
        validate_runtime_readiness(
            {
                "PORTFELL_EODHD_KEK_FILE": str(kek),
                "PORTFELL_OPERATIONS_EODHD_TOKEN_FILE": str(token),
                "PORTFELL_DATABASE_URL": "postgresql://portfell_app@postgres:5432/portfell",
            }
        )
    )


def test_runtime_readiness_rejects_a_non_postgres_database_url(tmp_path: Path) -> None:
    kek = tmp_path / "kek"
    token = tmp_path / "operations-token"
    kek.write_text("kek-material", encoding="utf-8")
    token.write_text("operations-token", encoding="utf-8")

    failures = failed_results(
        validate_runtime_readiness(
            {
                "PORTFELL_EODHD_KEK_FILE": str(kek),
                "PORTFELL_OPERATIONS_EODHD_TOKEN_FILE": str(token),
                "PORTFELL_DATABASE_URL": "sqlite:///portfell.db",
            }
        )
    )

    assert [failure.name for failure in failures] == ["runtime.database_url_configured"]


def test_database_readiness_requires_current_catalog_migrations() -> None:
    connection = FakeDatabaseConnection([(1,)])

    failures = failed_results(
        validate_database_readiness(
            "postgresql://portfell_app@postgres:5432/portfell", connect=lambda _: connection
        )
    )

    assert [failure.name for failure in failures] == ["database.catalog_current"]
    assert connection.closed


def test_database_readiness_redacts_connection_failure() -> None:
    def fail_connect(_: str) -> FakeDatabaseConnection:
        raise RuntimeError("database password must remain private")

    failures = failed_results(
        validate_database_readiness(
            "postgresql://portfell_app@postgres:5432/portfell", connect=fail_connect
        )
    )

    assert [failure.name for failure in failures] == [
        "database.connection_available",
        "database.catalog_current",
    ]


def test_database_readiness_cli_does_not_load_policy_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "portfell.hosted_readiness.validate_readiness",
        lambda: (_ for _ in ()).throw(AssertionError("policy evidence was loaded")),
    )
    monkeypatch.setattr("portfell.hosted_readiness.validate_database_readiness", lambda: [])

    assert main(("--require-database",)) == 0


def test_runtime_readiness_accepts_postgres_authority_when_hosting_is_approved(
    tmp_path: Path,
) -> None:
    kek = tmp_path / "kek"
    token = tmp_path / "operations-token"
    kek.write_text("kek-material", encoding="utf-8")
    token.write_text("operations-token", encoding="utf-8")

    failures = failed_results(
        validate_runtime_readiness(
            {
                "PORTFELL_EODHD_KEK_FILE": str(kek),
                "PORTFELL_OPERATIONS_EODHD_TOKEN_FILE": str(token),
                "PORTFELL_DATABASE_URL": "postgresql://portfell_app@postgres:5432/portfell",
                "PORTFELL_HOSTED_AUTHORITY": "postgres",
            }
        )
    )

    assert not failures


def test_runtime_readiness_cli_requires_nonempty_secret_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("PORTFELL_EODHD_KEK_FILE", str(tmp_path / "missing-kek"))
    monkeypatch.setenv("PORTFELL_OPERATIONS_EODHD_TOKEN_FILE", str(tmp_path / "missing-token"))
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://portfell_app@postgres:5432/portfell")

    assert main(("--require-runtime",)) == 1

    assert "runtime.external_kek_available" in capsys.readouterr().err


def test_runtime_readiness_cli_accepts_configured_postgres_authority(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    kek = tmp_path / "kek"
    token = tmp_path / "operations-token"
    kek.write_text("kek-material", encoding="utf-8")
    token.write_text("operations-token", encoding="utf-8")
    monkeypatch.setenv("PORTFELL_EODHD_KEK_FILE", str(kek))
    monkeypatch.setenv("PORTFELL_OPERATIONS_EODHD_TOKEN_FILE", str(token))
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://portfell_app@postgres:5432/portfell")
    monkeypatch.setenv("PORTFELL_HOSTED_AUTHORITY", "postgres")

    assert main(("--require-runtime",)) == 0

    assert capsys.readouterr().err == ""
