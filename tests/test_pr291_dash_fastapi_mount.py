from pathlib import Path

from portfell.hosted_dash_gateway import HostedDashGateway


ROOT = Path(__file__).resolve().parents[1]


def test_project_slug_matches_legacy_browser_route_semantics() -> None:
    assert HostedDashGateway.slug("München ETF Portfolio") == "munchen-etf-portfolio"
    assert HostedDashGateway.slug("  Project ++ 42  ") == "project-42"


def test_dash_package_does_not_import_hosted_or_postgres_authority() -> None:
    mount = (ROOT / "src/portfell/dash_ui/runtime/mount.py").read_text(encoding="utf-8")
    assert "portfell.hosted_api" not in mount
    assert "portfell.hosted_postgres" not in mount
    assert "portfell.hosted_dash_gateway" not in mount
    assert "DashResearchGateway" in mount


def test_hosted_composition_injects_gateway_into_dash_mount() -> None:
    source = (ROOT / "src/portfell/hosted_dash_runtime.py").read_text(encoding="utf-8")
    assert "create_runtime_app()" in source
    assert "HostedDashGateway(" in source
    assert "mount_dash_application(application, gateway)" in source


def test_runtime_entrypoint_uses_hosted_composition_root() -> None:
    source = (ROOT / "src/portfell/hosted_runtime.py").read_text(encoding="utf-8")
    assert "portfell.hosted_dash_runtime:create_runtime_app_with_dash" in source
    assert "portfell.dash_ui.runtime.mount:create_runtime_app_with_dash" not in source
