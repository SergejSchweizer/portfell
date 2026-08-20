from __future__ import annotations

from pathlib import Path


def test_pr292_apps_web_tree_is_fully_removed() -> None:
    assert not Path("apps/web").exists()


def test_pr292_python_api_worker_and_dash_assets_remain_present() -> None:
    required = (
        "apps/api/Dockerfile",
        "src/portfell/hosted_api.py",
        "src/portfell/hosted_runtime.py",
        "src/portfell/hosted_project_bootstrap_worker.py",
        "src/portfell/dash_ui/runtime/mount.py",
    )
    assert all(Path(path).is_file() for path in required)


def test_pr292_deletion_manifest_is_explicit_and_scoped_to_legacy_ui() -> None:
    manifest = Path("docs/cutover/pr292-react-node-deletion-manifest.md").read_text(
        encoding="utf-8"
    )
    assert "apps/web/package.json" in manifest
    assert "apps/web/vite.config.ts" in manifest
    assert "apps/web/src/pages/multivariate-statistics.tsx" in manifest
    assert "does not edit final Compose topology" in manifest
