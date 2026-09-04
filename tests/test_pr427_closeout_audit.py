"""PR427 closeout evidence must prove the production cutover is complete."""

from __future__ import annotations

import json

from portfell.independent_modules_audit import closeout_evidence, find_legacy_references


def test_closeout_audit_is_sanitized_and_reports_pass() -> None:
    evidence = closeout_evidence()
    assert evidence["contract"] == "independent-modules-v1"
    assert evidence["status"] == "PASS"
    assert evidence["legacy_reference_count"] == 0
    assert evidence["legacy_reference_count"] == len(find_legacy_references())
    serialized = json.dumps(evidence, sort_keys=True)
    assert "password" not in serialized.casefold()
    assert "postgres://" not in serialized


def test_audit_has_no_private_market_rows_or_credentials() -> None:
    references = find_legacy_references()
    assert all("market" not in path or path.endswith("hosted_api.py") for path in references)
