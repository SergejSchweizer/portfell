from migration_evidence import comparison_contract_evidence

from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS, SELECTION_V2_POLICY


def test_stage_one_independent_evidence_is_sanitized_and_exact() -> None:
    configurations = [item.to_row() for item in SELECTION_V2_CONFIGURATIONS]
    evidence = comparison_contract_evidence(
        sha="test-sha",
        configurations=configurations,
        policy=SELECTION_V2_POLICY.to_row(),
        focused_tests=["test_selection_v2_contract.py"],
    )
    assert evidence["comparison_configuration_count"] == 14
    assert evidence["comparison_split_policy"] == SELECTION_V2_POLICY.to_row()
    assert evidence["selection_authority"] == "legacy_lw_full"
    assert evidence["status"] == "PASS"
