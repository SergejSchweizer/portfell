"""PR427 closeout evidence must expose unfinished monolith dependencies."""

from __future__ import annotations

import json

from portfell.independent_modules_audit import closeout_evidence, find_legacy_references


def test_closeout_audit_is_sanitized_and_currently_blocks_false_pass() -> None:
    evidence = closeout_evidence()
    assert evidence["contract"] == "independent-modules-v1"
    assert evidence["status"] == "BLOCKED"
    assert evidence["legacy_reference_count"] == len(find_legacy_references())
    serialized = json.dumps(evidence, sort_keys=True)
    assert "password" not in serialized.casefold()
    assert "postgres://" not in serialized


def test_audit_has_no_private_market_rows_or_credentials() -> None:
    references = find_legacy_references()
    assert all("market" not in path or path.endswith("hosted_api.py") for path in references)
