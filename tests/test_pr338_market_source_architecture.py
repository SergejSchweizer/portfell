from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "market-source-architecture.md"


def test_market_source_architecture_freezes_external_postgres_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "10.10.1.3:54321",
        "database xetra_loader",
        "schema   xetra_loader",
        "listings, eod_quotes, dividends, splits",
        "(isin, exchange, code)",
        "REPEATABLE READ, READ ONLY",
        "Decimal",
        "adjusted_close",
        "missing_adjusted_close",
        "xetra_loader_sync",
        "NOLOGIN group role `portfell_app`",
    ):
        assert required in text


def test_market_source_architecture_marks_both_legacy_planes_transitional() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "React/Vite/TypeScript/TanStack" in text
    assert "current Portfell application database is transitional" in text
    assert "PR344–PR360" in text
    assert "portfell_dash" in text
    assert "PR356" in text
    assert "PR357" in text
    assert "PR358" in text
    assert "PR359" in text
    assert "PR360" in text


def test_document_does_not_make_loader_or_provider_a_portfell_runtime() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "never defined as a Portfell Compose service" in text
    assert "does not own a loader, refresh loop, provider client" in text
    assert "Provider acquisition and Portfell-owned market refresh never return" in text
