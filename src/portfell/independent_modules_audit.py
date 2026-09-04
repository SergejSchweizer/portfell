"""Machine-readable closeout audit for the independent-module cutover."""

from __future__ import annotations

from pathlib import Path

_PRODUCTION_ROOTS = ("src/portfell",)
_LEGACY_MARKERS = ("Research" + "ApplicationService", "mount_" + "dash_app")


def find_legacy_references(root: Path = Path("src/portfell")) -> tuple[str, ...]:
    """Return stable relative locations still requiring the final cutover."""

    matches: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in _LEGACY_MARKERS):
            matches.append(path.as_posix())
    return tuple(matches)


def closeout_evidence(root: Path = Path("src/portfell")) -> dict[str, object]:
    references = find_legacy_references(root)
    return {
        "contract": "independent-modules-v1",
        "status": "PASS" if not references else "BLOCKED",
        "legacy_reference_count": len(references),
        "legacy_references": list(references),
        "contract_version": "1",
        "migration_version": 6,
    }
