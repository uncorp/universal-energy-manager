"""Regression tests for the strict sensor-only Shadow UI."""

from __future__ import annotations

import inspect

from custom_components.universal_energy_manager import sensor


def test_shadow_sensor_module_exposes_no_switch_or_select_entities() -> None:
    """Shadow mode must not add any controllable UI platform."""
    source = inspect.getsource(sensor)
    assert "SwitchEntity" not in source
    assert "SelectEntity" not in source
    assert "async_turn_on" not in source
    assert "async_select_option" not in source


def test_shadow_sensor_module_has_no_control_entity_classes() -> None:
    """The prior inactive control placeholders must not regress."""
    assert not hasattr(sensor, "UemActiveSwitch")
    assert not hasattr(sensor, "UemStrategySelect")
