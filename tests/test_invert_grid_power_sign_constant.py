"""Slice 1 — test: CONF_INVERT_GRID_POWER_SIGN constant exists and is correct."""


from custom_components.universal_energy_manager.const import (
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_INVERT_GRID_POWER_SIGN,
)


class TestInvertGridPowerSignConstant:
    """Verify the new invert_grid_power_sign constant exists."""

    def test_constant_exists(self) -> None:
        """CONF_INVERT_GRID_POWER_SIGN must be defined."""
        assert CONF_INVERT_GRID_POWER_SIGN == "invert_grid_power_sign"

    def test_legacy_constant_still_exists(self) -> None:
        """CONF_GRID_POWER_SIGN_CONVENTION preserved for backward compat."""
        assert CONF_GRID_POWER_SIGN_CONVENTION == "grid_power_sign_convention"
