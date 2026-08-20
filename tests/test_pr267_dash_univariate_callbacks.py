from pathlib import Path


def test_pr267_registration_owns_start_poll_and_failure_projection() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/univariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    assert source.count("@app.callback") == 1
    assert "univariate-status-poll" in source
    assert "gateway.start_run(" in source
    assert "gateway.run_status(" in source
    assert "start_command_key(" in source
    assert '"failure"' in source


def test_pr267_start_uses_upstream_revision_and_selected_settings() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/univariate_statistics/registration.py"
    ).read_text(encoding="utf-8")
    assert 'get("metadata_selection_id")' in source
    assert '"dividend_frequencies"' in source
    assert "project_slug=project_slug" in source
