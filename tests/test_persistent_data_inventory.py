from __future__ import annotations

import json
from pathlib import Path

import pytest

from portfell.persistent_data_inventory import (
    InventoryError,
    inventory,
    reconcile,
    write_json_atomically,
)


def test_inventory_is_deterministic_and_captures_bytes_modes_and_hashes(tmp_path: Path) -> None:
    root = tmp_path / "lake"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    first = root / "a.txt"
    first.write_text("alpha", encoding="utf-8")
    first.chmod(0o640)
    (nested / "b.txt").write_text("beta", encoding="utf-8")

    result = inventory(root)

    assert result["file_count"] == 2
    assert result["total_bytes"] == 9
    assert [entry["path"] for entry in result["files"]] == ["a.txt", "nested/b.txt"]
    assert result["files"][0]["mode"] == "0640"
    assert len(result["content_hash"]) == 64


def test_reconcile_reports_missing_extra_and_changed_files(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "same").write_text("same", encoding="utf-8")
    (source / "changed").write_text("before", encoding="utf-8")
    (source / "missing").write_text("missing", encoding="utf-8")
    (target / "same").write_text("same", encoding="utf-8")
    (target / "changed").write_text("after", encoding="utf-8")
    (target / "extra").write_text("extra", encoding="utf-8")

    result = reconcile(source, target)

    assert not result["passed"]
    assert result["missing"] == ["missing"]
    assert result["extra"] == ["extra"]
    assert result["changed"] == ["changed"]


def test_inventory_rejects_symlinked_content(tmp_path: Path) -> None:
    root = tmp_path / "lake"
    root.mkdir()
    (root / "outside").symlink_to(tmp_path)

    with pytest.raises(InventoryError, match="symlink"):
        inventory(root)


def test_evidence_is_atomically_written_as_canonical_json(tmp_path: Path) -> None:
    destination = tmp_path / "evidence.json"

    write_json_atomically(destination, {"z": 1, "a": [True]})

    assert json.loads(destination.read_text(encoding="utf-8")) == {"a": [True], "z": 1}
