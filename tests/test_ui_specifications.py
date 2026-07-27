from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UI_DOCS = REPOSITORY_ROOT / "docs" / "ui"
MANIFEST = UI_DOCS / "manifest.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_ui_specification_manifest_lists_every_planned_page() -> None:
    manifest = _manifest()
    pages = manifest["pages"]

    assert manifest["version"] == "camovar-ui-spec-v1"
    assert [page["id"] for page in pages] == [
        "data",
        "metadata",
        "univariate",
        "filter",
        "diversification",
        "portfolio",
        "validation",
        "report",
        "settings",
        "account",
    ]
    for page in pages:
        assert (UI_DOCS / page["spec"]).exists()


def test_ui_specifications_cover_required_boundary_topics() -> None:
    texts = {path.name: path.read_text(encoding="utf-8") for path in UI_DOCS.glob("*.md")}
    joined = "\n".join(texts.values())

    for expected in (
        "financial calculations remain server-owned",
        "authorization decisions remain server-owned",
        "generic components",
        "feature components",
        "API clients",
        "loading, empty, warning, failed, and stale states",
        "keyboard-only operation",
        "desktop, tablet, and mobile",
        "provider keys",
        "session tokens",
        "internal storage paths",
    ):
        assert expected in joined


def test_ui_page_specs_cover_accepted_research_funnel_pages() -> None:
    pages_dir = UI_DOCS / "pages"
    page_text = {path.stem: path.read_text(encoding="utf-8") for path in pages_dir.glob("*.md")}

    for page_name in (
        "data",
        "metadata",
        "univariate",
        "filter",
        "diversification",
        "portfolio",
        "validation",
        "report",
        "settings",
        "account",
    ):
        assert page_name in page_text
        assert "User goal" in page_text[page_name]
        assert "Inputs" in page_text[page_name]
        assert "Outputs" in page_text[page_name]
