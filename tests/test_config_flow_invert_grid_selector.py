"""Slice 2 — test: grid sign selector changed from Select to BooleanSelector."""

import voluptuous as vol
from homeassistant.helpers.selector import BooleanSelector

from custom_components.universal_energy_manager.const import (
    CONF_INVERT_GRID_POWER_SIGN,
)


class TestInvertGridPowerSelector:
    """The grid sign convention field must be a BooleanSelector, not a vol.In Select."""

    def test_schema_has_invert_grid_key(self) -> None:
        """_mapping_defaults() must include CONF_INVERT_GRID_POWER_SIGN."""
        from custom_components.universal_energy_manager.config_flow import UemConfigFlow

        flow = UemConfigFlow()
        defaults = flow._mapping_defaults()
        assert CONF_INVERT_GRID_POWER_SIGN in defaults

    def test_schema_key_not_grid_sign_convention(self) -> None:
        """_mapping_defaults() must NOT include CONF_GRID_POWER_SIGN_CONVENTION."""
        from custom_components.universal_energy_manager.config_flow import UemConfigFlow
        from custom_components.universal_energy_manager.const import (
            CONF_GRID_POWER_SIGN_CONVENTION,
        )

        flow = UemConfigFlow()
        defaults = flow._mapping_defaults()
        assert CONF_GRID_POWER_SIGN_CONVENTION not in defaults

    def test_full_schema_invert_is_boolean_selector(self) -> None:
        """_build_full_schema() must use BooleanSelector for invert_grid_power_sign."""
        from custom_components.universal_energy_manager.config_flow import UemConfigFlow

        flow = UemConfigFlow()
        schema_dict = vol.Schema(flow._build_full_schema({})).schema

        invert_key = CONF_INVERT_GRID_POWER_SIGN
        assert invert_key in schema_dict, (
            f"Schema must contain {CONF_INVERT_GRID_POWER_SIGN}"
        )
        validator = schema_dict[invert_key]
        assert isinstance(
            validator, BooleanSelector
        ), f"Expected BooleanSelector, got {type(validator)}"

    def test_full_schema_no_grid_sign_convention_select(self) -> None:
        """_build_full_schema() must NOT contain a vol.In Select for grid sign."""
        from custom_components.universal_energy_manager.config_flow import UemConfigFlow
        from custom_components.universal_energy_manager.const import (
            CONF_GRID_POWER_SIGN_CONVENTION,
        )

        flow = UemConfigFlow()
        schema_dict = vol.Schema(flow._build_full_schema({})).schema

        assert CONF_GRID_POWER_SIGN_CONVENTION not in schema_dict, (
            f"Schema must NOT contain {CONF_GRID_POWER_SIGN_CONVENTION}"
        )

    def test_schema_invert_default_is_false(self) -> None:
        """Default value for invert_grid_power_sign must be False (Netzbezug = positive)."""
        from custom_components.universal_energy_manager.config_flow import UemConfigFlow

        flow = UemConfigFlow()
        defaults = flow._mapping_defaults()
        assert defaults[CONF_INVERT_GRID_POWER_SIGN] is False
