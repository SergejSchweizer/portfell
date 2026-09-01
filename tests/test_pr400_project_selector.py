from portfell.dash_app.project_selector import project_options, select_project


def test_project_options_include_all_universes_newest_first() -> None:
    universes = [
        {"universe_id": "older", "version": 1},
        {"universe_id": "newer", "version": 2},
    ]
    assert [item["value"] for item in project_options(universes)] == ["newer", "older"]
    assert select_project(universes)["universe_id"] == "newer"  # type: ignore[index]
    assert select_project(universes, "older")["universe_id"] == "older"  # type: ignore[index]


def test_empty_project_selector_is_read_only_and_disabled_by_model() -> None:
    assert project_options([]) == []
    assert select_project([]) is None
