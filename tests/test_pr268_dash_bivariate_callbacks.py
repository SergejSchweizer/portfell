from pathlib import Path


def test_pr268_registration_owns_start_poll_and_failure_projection() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/bivariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    assert source.count("@app.callback") == 1
    assert "bivariate-status-poll" in source
    assert "gateway.start_run(" in source
    assert "gateway.run_status(" in source
    assert "start_command_key(" in source
    assert '"failure"' in source


def test_pr268_start_is_scoped_to_persisted_univariate_selection() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/bivariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    assert 'get("univariate_selection_id")' in source
    assert "WorkflowId.BIVARIATE_STATISTICS" in source
    assert "project_slug=project_slug" in source
