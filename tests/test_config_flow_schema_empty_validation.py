"""Regression tests: _build_full_schema validates empty dict (Req 4).

Requirement 4 states:
- No entity or fixed capacity/power is mandatory
- OK/Speichern must work even with a completely empty form
- Entry stays in "Shadow – Einrichtung unvollständig" status

This test validates that the schema returned by _build_full_schema accepts
an empty dict {} without raising voluptuous.Invalid.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import voluptuous as vol

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)


def _make_flow() -> UemConfigFlow:
    """Create a minimal flow instance."""
    flow = UemConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.handler = DOMAIN
    ce = flow.hass.config_entries
    _all: dict[str, list] = {E3DC_RSCP_DOMAIN: [], DOMAIN: []}

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all.values():
                result.extend(entries)
            return result
        return _all.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


# =========================================================================== #
# TEST: Empty dict validates without error                                      #
# =========================================================================== #


class TestEmptySchemaValidation:
    """The _build_full_schema must accept an empty dict without validation errors."""

    def test_empty_dict_passes_schema_validation(self) -> None:
        """vol.Schema(schema_dict)({}) must not raise voluptuous.Invalid.

        The result may include defaults — the important thing is no exception.
        """
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        schema = vol.Schema(schema_dict)
        # This must NOT raise voluptuous.Invalid
        result = schema({})
        assert isinstance(result, dict)
        # All entity fields should be present (defaults applied)
        from custom_components.universal_energy_manager.const import (
            CONF_SOC_ENTITY,
        )
        assert result.get(CONF_SOC_ENTITY, "") == ""
        # Grid sign convention gets its default
        assert result.get("grid_power_sign_convention") == "positive_is_discharging_import"

    def test_whitespace_only_strings_pass(self) -> None:
        """Whitespace-only values should also be accepted (they are stripped
        later in the flow)."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        schema = vol.Schema(schema_dict)
        whitespace_input = {
            "soc_entity": "   ",
            "pv_power_entity": "   ",
            "house_power_entity": "   ",
            "battery_charge_entity": "   ",
            "battery_capacity_entity": "   ",
            "battery_manual_capacity_kwh": "   ",
            "max_charge_power_entity": "   ",
            "max_charge_manual_power_w": "   ",
            "grid_export_entity": "   ",
            "grid_power_sign_convention": "positive_is_discharging_import",
        }
        result = schema(whitespace_input)
        # Should accept whitespace strings
        assert result == whitespace_input

    def test_all_fields_can_be_empty_strings(self) -> None:
        """All entity fields can be empty strings, grid sign must have valid value."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        schema = vol.Schema(schema_dict)
        all_empty = {
            "soc_entity": "",
            "pv_power_entity": "",
            "house_power_entity": "",
            "battery_charge_entity": "",
            "battery_capacity_entity": "",
            "battery_manual_capacity_kwh": "",
            "max_charge_power_entity": "",
            "max_charge_manual_power_w": "",
            "grid_export_entity": "",
            "grid_power_sign_convention": "positive_is_discharging_import",
        }
        result = schema(all_empty)
        assert result == all_empty

    def test_completely_empty_dict_with_default_grid_sign(self) -> None:
        """An empty dict should be accepted and get default values from
        the schema defaults."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        schema = vol.Schema(schema_dict)
        result = schema({})
        # The key assertion is: no exception raised
        assert isinstance(result, dict)
        # Grid sign convention should get its default value
        assert result.get("grid_power_sign_convention") == "positive_is_discharging_import"
