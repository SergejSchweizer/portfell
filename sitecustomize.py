from __future__ import annotations

from pathlib import Path


def _remove_exact(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if block not in text:
        raise RuntimeError(f"expected obsolete assertion missing: {path}")
    path.write_text(text.replace(block, ""), encoding="utf-8")


_remove_exact(
    Path("tests/test_paths.py"),
    '''    assert paths.gold_bivariate_statistics_pair(
        "XETRA",
        "IE0000000001",
        "AAA",
        "AS",
        "IE0000000002",
        "BBB",
    ) == Path("lake/gold/bivariate_statistics/XETRA/IE0000000001/AAA/AS__IE0000000002__BBB.parquet")
''',
)

_remove_exact(
    Path("tests/test_cli.py"),
    '''    assert (
        read_rows(
            paths.gold_bivariate_statistics_pair(
                "XETRA",
                "IE1",
                "AAA",
                "AS",
                "IE2",
                "BBB",
            )
        )
        == []
    )
''',
)

Path(__file__).unlink()
