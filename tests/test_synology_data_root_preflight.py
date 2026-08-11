from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from portfell.synology_data_root_preflight import (
    REQUIRED_DIRECTORIES,
    _free_inodes_available,
    validate_data_root,
)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "portfell"
    for name in REQUIRED_DIRECTORIES:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def test_data_root_preflight_accepts_one_canonical_writable_tree(tmp_path: Path) -> None:
    root = _root(tmp_path)
    checks = validate_data_root(root, minimum_free_bytes=0, expected_root=root)

    assert all(check.passed for check in checks)


def test_data_root_preflight_rejects_missing_or_symlinked_directories(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "lake").rmdir()
    (root / "lake").symlink_to(tmp_path)

    checks = validate_data_root(root, minimum_free_bytes=0, expected_root=root)

    assert not {check.name for check in checks if check.passed} >= {
        "lake_exists",
        "lake_not_symlink",
    }


def test_data_root_preflight_requires_an_absolute_existing_root(tmp_path: Path) -> None:
    checks = validate_data_root(Path("relative-root"), minimum_free_bytes=0)

    assert {check.name for check in checks if not check.passed} == {"absolute", "exists"}


def test_data_root_preflight_rejects_an_unapproved_absolute_root(tmp_path: Path) -> None:
    root = _root(tmp_path)

    checks = validate_data_root(
        root, minimum_free_bytes=0, expected_root=Path("/volume2/docker/portfell")
    )

    assert "approved_root" in {check.name for check in checks if not check.passed}


def test_data_root_preflight_rejects_world_writable_storage_directory(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "backups").chmod(0o777)

    checks = validate_data_root(root, minimum_free_bytes=0, expected_root=root)

    assert "backups_not_world_writable" in {check.name for check in checks if not check.passed}


def test_free_inode_check_accepts_synology_filesystems_without_inode_accounting() -> None:
    assert _free_inodes_available(SimpleNamespace(f_files=0, f_favail=0))
    assert _free_inodes_available(SimpleNamespace(f_files=100, f_favail=1))
    assert not _free_inodes_available(SimpleNamespace(f_files=100, f_favail=0))
