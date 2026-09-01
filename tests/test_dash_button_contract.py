from __future__ import annotations

from collections.abc import Mapping

from portfell.dash_app.pages import bivariate, metadata, multivariate, univariate


def _button_ids(value: object) -> set[str]:
    """Collect HTML button IDs from a Dash component tree."""
    if hasattr(value, "to_plotly_json"):
        return _button_ids(value.to_plotly_json())  # type: ignore[no-any-return]
    found: set[str] = set()
    if isinstance(value, Mapping):
        props = value.get("props")
        if isinstance(props, Mapping):
            component_id = props.get("id")
            if isinstance(component_id, str) and props.get("children") is not None:
                component_type = value.get("type")
                if component_type == "Button":
                    found.add(component_id)
            found.update(_button_ids(props.get("children")))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_button_ids(child))
    return found


def test_every_workflow_button_has_a_stable_id() -> None:
    pages = (
        metadata.build_page(None),
        univariate.build_page(None),
        bivariate.build_page(None),
        multivariate.build_page(None),
    )
    actual = set().union(*(_button_ids(page.to_plotly_json()) for page in pages))
    assert actual == {
        "metadata-reset-filters",
        "metadata-delete-project",
        "metadata-create-universe",
        "univariate-preview-selection",
        "univariate-save-selection",
        "bivariate-compute",
        "multivariate-optimize",
    }
