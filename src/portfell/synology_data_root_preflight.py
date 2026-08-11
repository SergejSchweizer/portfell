"""Fail-closed preflight for the production Synology durable-data root."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REQUIRED_DIRECTORIES = ("postgres", "lake", "logs", "backups")


@dataclass(frozen=True)
class DataRootCheck:
    name: str
    passed: bool


def validate_data_root(root: Path, *, minimum_free_bytes: int) -> tuple[DataRootCheck, ...]:
    """Verify one absolute, non-symlinked root is ready before Compose mutation."""

    checks: list[DataRootCheck] = [
        DataRootCheck("absolute", root.is_absolute()),
        DataRootCheck("exists", root.is_dir()),
        DataRootCheck("not_symlink", not root.is_symlink()),
    ]
    if not all(check.passed for check in checks):
        return tuple(checks)
    resolved_root = root.resolve(strict=True)
    checks.append(DataRootCheck("canonical", resolved_root == root))
    for name in REQUIRED_DIRECTORIES:
        directory = root / name
        checks.extend(
            (
                DataRootCheck(f"{name}_exists", directory.is_dir()),
                DataRootCheck(f"{name}_not_symlink", not directory.is_symlink()),
            )
        )
    if not all(check.passed for check in checks):
        return tuple(checks)
    available_bytes = os.statvfs(root).f_bavail * os.statvfs(root).f_frsize
    checks.append(DataRootCheck("free_space", available_bytes >= minimum_free_bytes))
    checks.append(DataRootCheck("atomic_replace", _atomic_replace_supported(root / "lake")))
    return tuple(checks)


def _atomic_replace_supported(directory: Path) -> bool:
    try:
        with tempfile.TemporaryDirectory(dir=directory, prefix=".portfell-preflight-") as temp:
            root = Path(temp)
            source, destination = root / "source", root / "destination"
            source.write_text("probe", encoding="utf-8")
            source.replace(destination)
            return destination.read_text(encoding="utf-8") == "probe"
    except OSError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the immutable Portfell production data root."
    )
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PORTFELL_DATA_ROOT", "")))
    parser.add_argument("--minimum-free-gib", type=int, default=20)
    args = parser.parse_args(argv)
    checks = validate_data_root(args.root, minimum_free_bytes=args.minimum_free_gib * 1024**3)
    print(
        json.dumps(
            {
                "passed": all(check.passed for check in checks),
                "checks": [check.__dict__ for check in checks],
            }
        )
    )
    return 0 if all(check.passed for check in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
