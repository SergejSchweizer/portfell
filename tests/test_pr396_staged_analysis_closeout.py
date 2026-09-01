from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/staged-analysis-performance-v1.md"


def test_closeout_freezes_workflow_and_bounded_ux_contract() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "Metadata → full-universe Univariate",
        "committed",
        "Selection → Bivariate",
        "default-objective Multivariate",
        "all eight ordered",
        "≤100 table rows",
        "≤500 Univariate chart points",
        "≤1000 Bivariate chart points",
        "≤512 KiB",
        "1440×900",
        "1024×768",
        "390×844",
    ):
        assert marker in text


def test_closeout_freezes_latency_and_sanitization_rules() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "30 samples",
        "≤750 ms",
        "≤400 ms",
        "≤200 ms",
        "≤1000 ms",
        "25%",
        "exact 40-hex Git SHA",
        "Credentials",
        "Skipped or cancelled",
    ):
        assert marker in text
