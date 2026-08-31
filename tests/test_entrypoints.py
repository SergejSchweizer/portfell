"""Installed console-script entry-point consistency and smoke gate (C01)."""

from __future__ import annotations

import importlib
import sys
from importlib import metadata

import pytest

PORTFELL_ENTRY_POINTS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (entry_point.name, entry_point.value)
        for entry_point in metadata.entry_points(group="console_scripts")
        if entry_point.name == "portfell" or entry_point.name.startswith("portfell-")
    )
)


def test_portfell_console_scripts_are_registered() -> None:
    names = {name for name, _value in PORTFELL_ENTRY_POINTS}
    assert names == {
        "portfell-docs-refresh",
        "portfell-quality",
    }
    assert "portfell" not in names


@pytest.mark.parametrize("name,value", PORTFELL_ENTRY_POINTS)
def test_console_script_target_imports_and_is_callable(name: str, value: str) -> None:
    module_path, _, attribute = value.partition(":")
    module = importlib.import_module(module_path)
    target = getattr(module, attribute)
    assert callable(target), f"{name} -> {value} is not callable"


@pytest.mark.parametrize("name,value", PORTFELL_ENTRY_POINTS)
def test_console_script_help_exits_cleanly_without_side_effects(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", [name, "--help"])
    module_path, _, attribute = value.partition(":")
    module = importlib.import_module(module_path)
    target = getattr(module, attribute)

    with pytest.raises(SystemExit) as excinfo:
        target()

    assert excinfo.value.code == 0
