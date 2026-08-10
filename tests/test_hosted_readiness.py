from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

from portfell.hosted_readiness import (
    MANDATORY_DECISIONS,
    failed_results,
    load_readiness,
    local_only_mode_allowed,
    public_hosted_mode_allowed,
    validate_readiness,
    validate_runtime_readiness,
)


def test_hosted_readiness_records_cover_every_mandatory_decision() -> None:
    payload = load_readiness()
    decisions = {row["id"] for row in payload["decisions"]}

    assert decisions == set(MANDATORY_DECISIONS)
    failures = failed_results(validate_readiness(payload, today=date(2026, 8, 10)))

    assert {failure.name for failure in failures} == {
        "decision.shared-data-provider-license.approved",
        "decision.shared-data-provider-license.approved_uses",
    }
    assert local_only_mode_allowed(payload, today=date(2026, 8, 10))
    assert not public_hosted_mode_allowed(payload, today=date(2026, 8, 10))


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
            }
        )
    )
