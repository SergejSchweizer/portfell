"""Hash-based inventory and reconciliation for a quiesced Portfell data tree.

The module deliberately never copies, deletes, or restores data.  It supplies
the deterministic evidence required before and after an operator-controlled
cutover, while the actual backup encryption key stays outside the repository
and the data root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


class InventoryError(ValueError):
    """Raised when a data tree cannot be safely inventoried."""


def inventory(root: Path) -> dict[str, Any]:
    """Return a deterministic, content-addressed inventory of regular files.

    Symlinks, non-regular entries and a missing root are rejected: following
    either could turn a reconciliation into an inventory of unrelated host
    data.  Empty directories intentionally do not affect shared-data parity.
    """

    resolved = _validated_root(root)
    files = [_file_record(resolved, candidate) for candidate in _regular_files(resolved)]
    encoded = _canonical_json(files).encode("utf-8")
    return {
        "root": str(resolved),
        "file_count": len(files),
        "total_bytes": sum(record["bytes"] for record in files),
        "content_hash": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


def reconcile(source: Path, target: Path) -> dict[str, Any]:
    """Compare two inventories and return a machine-readable parity result."""

    source_inventory = inventory(source)
    target_inventory = inventory(target)
    source_files = {item["path"]: item for item in source_inventory["files"]}
    target_files = {item["path"]: item for item in target_inventory["files"]}
    missing = sorted(set(source_files) - set(target_files))
    extra = sorted(set(target_files) - set(source_files))
    changed = sorted(
        path
        for path in set(source_files) & set(target_files)
        if source_files[path] != target_files[path]
    )
    return {
        "passed": not (missing or extra or changed),
        "source": source_inventory,
        "target": target_inventory,
        "missing": missing,
        "extra": extra,
        "changed": changed,
    }


def write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    """Write redacted evidence atomically below an existing safe directory."""

    parent = path.parent.resolve(strict=True)
    if parent.is_symlink() or not parent.is_dir():
        raise InventoryError("evidence parent must be an existing real directory")
    body = _canonical_json(payload) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _validated_root(root: Path) -> Path:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise InventoryError("inventory root must be an absolute existing non-symlink directory")
    return root.resolve(strict=True)


def _regular_files(root: Path) -> Iterable[Path]:
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise InventoryError(f"symlink is not allowed in inventory: {candidate}")
        if candidate.is_file():
            yield candidate
        elif not candidate.is_dir():
            raise InventoryError(f"non-regular entry is not allowed in inventory: {candidate}")


def _file_record(root: Path, candidate: Path) -> dict[str, Any]:
    metadata = candidate.stat()
    return {
        "path": candidate.relative_to(root).as_posix(),
        "bytes": metadata.st_size,
        "mode": format(metadata.st_mode & 0o7777, "04o"),
        "sha256": _sha256(candidate),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory or reconcile quiesced Portfell data.")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory_command = commands.add_parser("inventory")
    inventory_command.add_argument("--root", required=True, type=Path)
    inventory_command.add_argument("--output", type=Path)
    reconcile_command = commands.add_parser("reconcile")
    reconcile_command.add_argument("--source", required=True, type=Path)
    reconcile_command.add_argument("--target", required=True, type=Path)
    reconcile_command.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            payload = inventory(args.root)
        else:
            payload = reconcile(args.source, args.target)
    except InventoryError as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 2
    if args.output is not None:
        write_json_atomically(args.output, payload)
    print(_canonical_json(payload))
    return 0 if args.command == "inventory" or payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
