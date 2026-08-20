from pathlib import Path


def test_pr266_registration_owns_metadata_actions_and_uses_typed_gateway() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/metadata_builder/registration.py"
    ).read_text(encoding="utf-8")
    assert source.count("@app.callback") == 2
    assert 'command="fetch_metadata"' in source
    assert 'command="create_project"' in source
    assert "gateway.start_run(" in source
    assert "WorkflowId.METADATA_BUILDER" in source
    assert "provider" not in source.casefold()
    assert "postgres" not in source.casefold()


def test_pr266_registration_captures_exact_five_builder_criteria() -> None:
    source = Path(
        "src/portfell/dash_ui/callbacks/metadata_builder/registration.py"
    ).read_text(encoding="utf-8")
    for suffix in ("exchange", "instrument-type", "country", "currency", "name-contains"):
        assert f'component_id(METADATA_NAMESPACE, "{suffix}")' in source
