"""Fail-closed preflight for the production UGREEN NAS durable-data root."""

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


def validate_data_root(
    root: Path, *, minimum_free_bytes: int, expected_root: Path | None = None
) -> tuple[DataRootCheck, ...]:
    """Verify one absolute, non-symlinked root is ready before Compose mutation."""

    checks: list[DataRootCheck] = [
        DataRootCheck("absolute", root.is_absolute()),
        DataRootCheck("approved_root", expected_root is None or root == expected_root),
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
                DataRootCheck(f"{name}_not_world_writable", _not_world_writable(directory)),
            )
        )
    if not all(check.passed for check in checks):
        return tuple(checks)
    filesystem = os.statvfs(root)
    available_bytes = filesystem.f_bavail * filesystem.f_frsize
    checks.append(DataRootCheck("free_space", available_bytes >= minimum_free_bytes))
    checks.append(DataRootCheck("free_inodes", _free_inodes_available(filesystem)))
    checks.append(DataRootCheck("root_not_world_writable", _not_world_writable(root)))
    for name in ("lake", "logs", "backups"):
        checks.append(DataRootCheck(f"{name}_write_probe", _write_probe(root / name)))
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


def _not_world_writable(path: Path) -> bool:
    """Reject a data directory that any host user can modify."""

    try:
        return path.stat().st_mode & 0o002 == 0
    except OSError:
        return False


def _free_inodes_available(filesystem: os.statvfs_result) -> bool:
    """Accept filesystems that explicitly do not report an inode budget.

    UGREEN NAS filesystems can report both inode fields as zero even when
    storage is writable and inode exhaustion is not a meaningful capacity
    signal. A non-zero total keeps the normal fail-closed availability check.
    """

    return filesystem.f_files == 0 or filesystem.f_favail > 0


def _write_probe(directory: Path) -> bool:
    """Prove that the service user can create and remove a private probe."""

    try:
        with tempfile.TemporaryDirectory(dir=directory, prefix=".portfell-write-probe-"):
            return True
    except OSError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the immutable Portfell production data root."
    )
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("PORTFELL_DATA_ROOT", "")))
    parser.add_argument("--minimum-free-gib", type=int, default=20)
    parser.add_argument("--expected-root", type=Path, default=Path("/volume2/docker/portfell"))
    args = parser.parse_args(argv)
    checks = validate_data_root(
        args.root,
        minimum_free_bytes=args.minimum_free_gib * 1024**3,
        expected_root=args.expected_root,
    )
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
