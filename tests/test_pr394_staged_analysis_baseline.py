from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READ_PLANE = ROOT / "docs/contracts/staged-analysis-read-plane-v1.md"
EVIDENCE = ROOT / "docs/evidence/staged-analysis-performance-baseline-v1.md"


def test_baseline_evidence_freezes_fixture_and_budgets() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "5,000",
        "400-member",
        "100,000",
        "30 warm samples",
        "1,500 ms",
        "800 ms",
        "400 ms",
        "2,000 ms",
        "SQL query",
        "callback payload bytes",
    ):
        assert marker in text


def test_baseline_reuses_frozen_read_plane_contract() -> None:
    text = READ_PLANE.read_text(encoding="utf-8")
    for marker in (
        "Filter preview is read-only",
        "Univariate chart-point cap: `500`",
        "Bivariate chart-point cap: `1000`",
        "`<= 512 KiB`",
        "Previous selection",
        "call `run_detail()` as its normal data source",
    ):
        assert marker in text
