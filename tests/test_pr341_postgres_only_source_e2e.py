from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "portfell"
FOUR_STAGE = ROOT / "tests" / "test_four_stage_market_source_qa.py"


def test_cold_runtime_has_no_provider_nas_medallion_or_loader_python_authority() -> None:
    assert not (PACKAGE / "cli.py").exists()
    assert not (PACKAGE / "workflows.py").exists()

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    runtime = (PACKAGE / "hosted_runtime.py").read_text(encoding="utf-8").lower()
    runtime_image = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8").lower()
    for forbidden in (
        "eodhd",
        "eodhistoricaldata",
        "import xetra_loader",
        "from xetra_loader",
        "market bronze",
        "market silver",
        "market gold",
        "market-nas",
    ):
        assert forbidden not in pyproject
        assert forbidden not in compose
        assert forbidden not in runtime
        assert forbidden not in runtime_image


def test_four_stage_e2e_covers_full_identity_lineage_and_fail_closed_inputs() -> None:
    source = FOUR_STAGE.read_text(encoding="utf-8")
    required_tests = (
        "test_four_stage_market_source_contract_has_full_identity_and_one_lineage",
        "test_four_stage_market_source_fails_closed_for_missing_adjusted_close",
        "test_bivariate_fails_closed_when_the_source_has_no_common_return_history",
    )
    for name in required_tests:
        assert f"def {name}" in source

    # Duplicate ISINs survive as distinct full identities.
    assert 'ListingKey("IE00QA000001", "XETRA", "QA-A")' in source
    assert 'ListingKey("IE00QA000001", "XETRA", "QA-B")' in source
    assert '"IE00QA000001:XETRA:QA-A"' in source
    assert '"IE00QA000001:XETRA:QA-B"' in source

    # One deterministic source lineage is propagated downstream and never replaced
    # with provider/download/sync identity.
    assert 'snapshot_id.startswith("market_source_snapshot_")' in source
    assert 'assert bivariate_run.source_id.endswith(snapshot_id)' in source
    assert 'computed.summary["market_source_snapshot_id"] == snapshot_id' in source
    assert 'assert source_before == gateway.snapshot' in source
    lowered = source.lower()
    assert "provider_download" not in lowered
    assert "quote_run_id" not in lowered
    assert "xetra_loader_sync" not in lowered


def test_all_production_market_sql_is_gateway_repository_owned() -> None:
    offenders: list[str] = []
    allowed_root = PACKAGE / "market_source"
    for path in PACKAGE.rglob("*.py"):
        if allowed_root in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value.lower()
            if "xetra_loader." in literal and any(
                token in literal
                for token in (
                    "select ",
                    "insert ",
                    "update ",
                    "delete ",
                    "truncate ",
                    "alter ",
                    "create ",
                    "drop ",
                )
            ):
                offenders.append(str(path.relative_to(ROOT)))
                break
    assert offenders == []


def test_gateway_contract_is_select_only_and_short_lived() -> None:
    gateway = (PACKAGE / "market_source" / "gateway.py").read_text(encoding="utf-8")
    connection = (PACKAGE / "market_source" / "connection.py").read_text(encoding="utf-8")

    assert "repeatable_read_snapshot" in gateway
    assert "REPEATABLE READ READ ONLY" in connection
    assert "SET LOCAL TIME ZONE 'UTC'" in connection
    assert "connection.close()" in connection

    combined = f"{gateway}\n{connection}".upper()
    for forbidden in (
        "INSERT INTO XETRA_LOADER",
        "UPDATE XETRA_LOADER",
        "DELETE FROM XETRA_LOADER",
        "TRUNCATE XETRA_LOADER",
    ):
        assert forbidden not in combined


def test_repeated_workflow_is_source_immutable_by_contract() -> None:
    source = FOUR_STAGE.read_text(encoding="utf-8")
    assert "source_before = gateway.snapshot" in source
    assert "assert source_before == gateway.snapshot" in source
    assert "gateway.snapshot_reads >= 6" in source


def test_partial_and_missing_values_are_not_zero_fallbacks() -> None:
    source = FOUR_STAGE.read_text(encoding="utf-8")
    projection = (PACKAGE / "market_source" / "projection.py").read_text(encoding="utf-8")

    assert "MISSING_ADJUSTED_CLOSE" in source
    assert "MISSING_ADJUSTED_CLOSE" in projection
    assert "raw close" in source.lower()
    assert "failed.rows == ()" in source
