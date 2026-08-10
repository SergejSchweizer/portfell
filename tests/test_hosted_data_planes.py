from __future__ import annotations

from dataclasses import replace

import pytest

from portfell.hosted_data_planes import (
    FORBIDDEN_SHARED_PAYLOAD_FIELDS,
    DataPlaneContractError,
    FullListingIdentity,
    load_ownership_matrix,
    validate_ownership_matrix,
)


def test_d017_ownership_matrix_is_complete_and_tenant_neutral() -> None:
    matrix = load_ownership_matrix()

    assert validate_ownership_matrix(matrix) == ()
    assert set(matrix["forbidden_shared_payload_fields"]) == FORBIDDEN_SHARED_PAYLOAD_FIELDS
    assert matrix["authorization"]["shared_object_existence_is_authorization"] is False


def test_d017_ownership_matrix_rejects_shared_tenant_fields() -> None:
    matrix = load_ownership_matrix()
    matrix["forbidden_shared_payload_fields"] = ["user_id"]

    assert validate_ownership_matrix(matrix) == ("forbidden_shared_payload_fields",)


def test_full_listing_identity_requires_every_canonical_component() -> None:
    listing = FullListingIdentity("eodhd", "XETRA", "IE0000000001", "AAA")

    assert listing.row() == {
        "provider": "eodhd",
        "exchange": "XETRA",
        "isin": "IE0000000001",
        "code": "AAA",
    }
    with pytest.raises(DataPlaneContractError, match="full_listing_identity_required"):
        replace(listing, code="")
