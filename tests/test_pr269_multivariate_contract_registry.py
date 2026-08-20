from __future__ import annotations

import math
from pathlib import Path

import pytest

from portfell.multivariate.contracts.common import (
    DECISION_STAGE_ORDER,
    AttemptEnvelope,
    DecisionStageId,
    EvidenceAvailability,
    ListingIdentity,
)
from portfell.multivariate.contracts.serialization import canonical_json


def test_pr269_listing_identity_uses_all_three_listing_fields() -> None:
    xetra = ListingIdentity("DE000A", "XETRA", "AAA")
    lse = ListingIdentity("DE000A", "LSE", "AAA")
    assert xetra != lse
    assert xetra.token == "DE000A|XETRA|AAA"
    with pytest.raises(ValueError):
        ListingIdentity("DE000A", "", "AAA")


def test_pr269_decision_stage_registry_is_exact_and_ordered() -> None:
    assert DECISION_STAGE_ORDER == (
        DecisionStageId.INPUT_ELIGIBILITY,
        DecisionStageId.UNIVARIATE_PARETO,
        DecisionStageId.BIVARIATE_REDUNDANCY,
        DecisionStageId.RISK_MODEL_CANDIDATES,
        DecisionStageId.PORTFOLIO_CANDIDATES,
        DecisionStageId.WALK_FORWARD_VALIDATION,
        DecisionStageId.WINNER_SELECTION,
        DecisionStageId.FINAL_PORTFOLIO,
    )


def test_pr269_canonical_json_is_order_invariant_and_finite_only() -> None:
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="NaN/Inf"):
            canonical_json({"metric": value})


def test_pr269_public_serialization_rejects_secrets_tokens_paths_and_objects() -> None:
    for key in ("password", "api_token", "credential_id", "storage_path"):
        with pytest.raises(ValueError, match="forbidden public evidence key"):
            canonical_json({key: "redacted"})
    with pytest.raises(TypeError, match="unsupported canonical value"):
        canonical_json({"value": object()})


def test_pr269_attempt_envelope_rejects_error_on_available_evidence() -> None:
    with pytest.raises(ValueError):
        AttemptEnvelope("run-1", 1, EvidenceAvailability.AVAILABLE, error_code="secret_error")


def test_pr269_protocol_layer_has_no_provider_or_storage_authority_imports() -> None:
    source = Path("src/portfell/multivariate/contracts/protocols.py").read_text(encoding="utf-8")
    forbidden = ("postgres", "database", "eodhd", "provider", "filesystem", "storage_uri")
    assert not any(token in source.casefold() for token in forbidden)
