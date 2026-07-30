"""TDD: Cover config_flow.py elif branch (prefill preservation).

The entity_data merge loop has this structure:
    for field in set(list(entity_data.keys()) + list(user_input.keys())):
        if field in user_input and isinstance(user_input[field], str):
            entity_data[field] = user_input[field].strip()
        elif field in user_input:
            entity_data[field] = user_input[field]
        elif field in entity_data:
            pass  # keep prefill value  <-- uncovered branch

This branch is taken when a field exists in the prefill (entity_data)
but is NOT submitted by the user in user_input. Previously, tests always
submitted all fields, so this elif was never exercised.

TDD: test first (expect fail), implement, verify green.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _make_flow(hass: MagicMock, e3dc_entries: list = None) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    ce = hass.config_entries
    _all = {E3DC_RSCP_DOMAIN: e3dc_entries or [], DOMAIN: []}

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


def _mock_location(hass: MagicMock):
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


class TestConfigFlowBranch346PrefillPreservation:
    """Line 346: elif field in entity_data → pass (keep prefill).

    This test submits ONLY core entities, leaving all optional fields
    (invert_grid_power_sign, battery_manual_capacity_kwh,
    max_charge_manual_power_w, etc.)
    to be filled from the prefill. The elif branch at line 346 must
    preserve those prefill values.
    """

    def test_prefill_values_preserved_via_elif_branch_346(self) -> None:
        """Submit core entities only; optional fields kept from prefill
        via the elif branch (line 346) that does 'pass'."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        # Step 1: no_e3dc_choice → manual_mapping
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        # Step 2: manual_mapping with ONLY core entities.
        # The prefill from no_e3dc_choice includes all optional fields
        # with defaults (invert_grid_power_sign, etc.).
        # By omitting optional fields from user_input, the elif branch
        # at line 346 (elif field in entity_data: pass) must preserve them.
        minimal_data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
        }
        result = _run(flow.async_step_manual_mapping(minimal_data))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Core entities submitted
        assert result["data"][CONF_SOC_ENTITY] == "sensor.manual_soc"
        # Optional fields must have been preserved from prefill (elif branch)
        # The prefill sets invert_grid_power_sign to default (Netzbezug)
        expected = False
        actual = result["data"].get(CONF_INVERT_GRID_POWER_SIGN)
        assert actual == expected
