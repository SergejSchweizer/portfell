from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"


def test_fixture_catalogue_is_versioned_and_contains_expected_scenarios() -> None:
    scenarios = (WEB_ROOT / "src" / "fixtures" / "scenarios.ts").read_text(encoding="utf-8")

    for expected in (
        "empty-user",
        "missing-credential",
        "invalid-credential",
        "free-key",
        "paid-key",
        "empty-project",
        "partial-data",
        "statistics-running",
        "statistics-complete",
        "stale-analysis",
        "provider-error",
        "authorization-error",
        "portfolio-comparison",
        "stress-warning",
        "recommendation-ready",
        "slow-api",
        "offline-recovery",
    ):
        assert expected in scenarios

    assert "fixtureScenarioNames" in scenarios
    assert "function mockResponseFor" in scenarios


def test_mock_api_is_explicitly_gated_to_local_dev_or_test_modes() -> None:
    mock_api = (WEB_ROOT / "src" / "mock-api.ts").read_text(encoding="utf-8")
    env = (WEB_ROOT / "src" / "env.ts").read_text(encoding="utf-8")
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    selector = (WEB_ROOT / "src" / "components" / "fixture-selector.tsx").read_text(
        encoding="utf-8"
    )
    shell = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")

    assert 'uiFixtureMode === "test" || env.uiFixtureMode === "local-dev"' in mock_api
    assert "VITE_CAMOVAR_UI_FIXTURE" in env
    assert "VITE_CAMOVAR_UI_FIXTURE_MODE" in env
    assert "canSelectUiFixture(env.uiFixtureMode)" in selector
    assert "FixtureSelector" in shell
    assert "maybeMockJson<T>(path, init)" in client
    assert "if (mocked !== null) return mocked;" in client


def test_fixture_contracts_remain_typed_and_keyed_by_shared_api_shapes() -> None:
    contracts = (WEB_ROOT / "src" / "contracts.ts").read_text(encoding="utf-8")

    for expected in (
        "ApiSession",
        "ApiCredentialStatus",
        "ApiProject",
        "ApiProjects",
        "ApiFieldOptions",
        "ApiProgress",
        "ApiUnivariateSummaryRow",
        "ApiUnivariateSummary",
    ):
        assert expected in contracts


def test_fixture_selector_uses_url_query_only_in_allowed_modes() -> None:
    env = (WEB_ROOT / "src" / "env.ts").read_text(encoding="utf-8")

    assert 'new URL(window.location.href).searchParams.get("fixture")' in env
    assert 'uiFixtureMode === "test" || uiFixtureMode === "local-dev"' in env
    assert 'return mode === "test" || mode === "local-dev"' in env
