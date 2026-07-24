"""TDD tests for remaining narrow edge cases in config_flow.

Covers:
- config_flow.py:323 – manual_mapping when prefill is None
- config_flow.py:423 – manual mapping uid generation when location is None
- config_flow.py:448 – reconfigure when entry is None
- config_flow.py:555 – _get_current_entry returning from _async_current_entries
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _make_flow_no_hass() -> UemConfigFlow:
    """Create a flow with minimal mock hass."""
    flow = UemConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.handler = DOMAIN
    ce = flow.hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: [],
        FORECAST_SOLAR_DOMAIN: [],
    }

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


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# =========================================================================== #
# TEST: manual_mapping with prefill=None                                     #
# =========================================================================== #


class TestManualMappingNoPrefill:
    """manual_mapping when _prefill_data is None should not crash."""

    def test_manual_mapping_prefill_none_sets_empty_prefill(self) -> None:
        """When _prefill_data is None, manual_mapping sets it to {} and shows
        the form (lines 322-323 of config_flow.py)."""
        flow = _make_flow_no_hass()
        flow._prefill_data = None

        result = _run(flow.async_step_manual_mapping())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"
        # prefill should now be an empty dict, not None
        assert flow._prefill_data == {}


# =========================================================================== #
# TEST: manual_mapping uid when location is None                             #
# =========================================================================== #


class TestManualMappingNoLocation:
    """Manual mapping uid generation should handle missing location."""

    def test_manual_mapping_uid_without_location(self) -> None:
        """When hass.config.location is None, uid uses id(self) fallback
        (line 423 of config_flow.py)."""
        flow = _make_flow_no_hass()
        # Remove location entirely
        del flow.hass.config.location

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
        }
        result = _run(flow.async_step_manual_mapping(data))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] is None
        assert result["data"].get(CONF_MANUAL_ENTITIES) is True


# =========================================================================== #
# TEST: reconfigure when entry is None                                       #
# =========================================================================== #


class TestReconfigureNoEntry:
    """Reconfigure with no entry should abort."""

    def test_reconfigure_abort_when_no_entry(self) -> None:
        """When _get_current_entry returns None, reconfigure aborts with
        'not_configured' (line 448 of config_flow.py)."""
        flow = _make_flow_no_hass()
        flow.context = {"entry_id": "nonexistent"}

        with patch.object(UemConfigFlow, "_get_current_entry", return_value=None):
            result = _run(flow.async_step_reconfigure())

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_configured"


# =========================================================================== #
# TEST: _get_current_entry via _async_current_entries                        #
# =========================================================================== #


class TestGetCurrentEntryFallback:
    """_get_current_entry falls back to _async_current_entries."""

    def test_get_current_entry_from_async_current_entries(self) -> None:
        """When context has no entry_id, _get_current_entry uses
        _async_current_entries (line 555 of config_flow.py)."""
        flow = _make_flow_no_hass()
        flow.context = {}  # No entry_id

        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={},
            source="user",
            entry_id="uem-fallback",
            unique_id="uem:manual:test",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow._async_current_entries = MagicMock(return_value=[uem_entry])

        result = flow._get_current_entry()
        assert result is uem_entry
