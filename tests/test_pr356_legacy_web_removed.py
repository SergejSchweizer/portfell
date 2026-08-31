from __future__ import annotations

from pathlib import Path

import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_react_application_and_driver_are_absent() -> None:
    assert not (ROOT / "apps" / "web").exists()
    assert not (ROOT / "scripts" / "run_real_stack_e2e.sh").exists()
    assert not (ROOT / "src" / "portfell" / "compose_web_watch.py").exists()
    assert not (ROOT / "compose.e2e.yaml").exists()
    for test_name in (
        "test_frontend_backend_contracts.py",
        "test_hosted_web_ui.py",
        "test_watch_compose_web.py",
        "test_web_react_scaffold.py",
    ):
        assert not (ROOT / "tests" / test_name).exists()


def test_runtime_and_project_metadata_have_no_first_party_node_boundary() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"api", "postgres"}

    rendered_compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    rendered_env = (ROOT / ".env.example").read_text(encoding="utf-8").lower()
    assert "portfell_web_port" not in rendered_env
    assert "apps/web" not in rendered_compose
    assert "npm" not in rendered_compose
    assert "node" not in rendered_compose

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    assert "portfell-compose-web-watch" not in scripts
    assert "portfell-compose-watch" not in scripts
