from pathlib import Path


def test_pr289_registration_owns_objective_start_poll_and_stale_projection() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/multivariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    assert source.count("@app.callback") == 1
    assert "OBJECTIVE_SELECTOR_ID" in source
    assert "RunStatus.STALE" in source
    assert "gateway.start_run(" in source
    assert "gateway.run_status(" in source
    assert "gateway.multivariate_settings(" in source
    assert "optimizer_command_key(" in source


def test_pr289_start_preserves_persisted_constraints_and_upstream_identity() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/multivariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    for field in (
        "allowed_distribution_frequencies",
        "min_weight",
        "max_weight",
        "max_holdings",
        "transaction_cost_rate",
    ):
        assert f'"{field}"' in source
    assert 'get("bivariate_revision")' in source
    assert 'get("bivariate_run_id")' in source
