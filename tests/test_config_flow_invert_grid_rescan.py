"""Regression: CONF_INVERT_GRID_POWER_SIGN preserved during _rescan_e3dc.

CONF_INVERT_GRID_POWER_SIGN is NOT a mapping field (not in _ENT_MAP_LOOKUP).
During _rescan_e3dc the code only updates mapping fields from discovery.
This test proves the invert flag is never silently overwritten.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap

# --------------------------------------------------------------------------- #
# Helpers                                                                        #
# --------------------------------------------------------------------------- #


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title=title,
        data={},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# =========================================================================== #
# TEST: CONF_INVERT_GRID_POWER_SIGN preserved during _rescan_e3dc              #
# =========================================================================== #


class TestInvertGridSignRescanPreserved:
    """CONF_INVERT_GRID_POWER_SIGN must survive _rescan_e3dc unchanged."""

    def test_rescan_preserves_invert_true(self) -> None:
        """Existing entry with invert=True must keep True after rescan."""
        e3dc_entry = _make_e3dc_entry()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "S10E-12345",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                CONF_INVERT_GRID_POWER_SIGN: True,
            },
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {"entry_id": "uem-001"}
        flow.handler = DOMAIN

        all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: [e3dc_entry]}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        def _mock_discover(_self, _entry_id):
            return full_map

        with patch.object(UemConfigFlow, "_discover_entities", _mock_discover):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY

        # The key assertion: invert flag must be preserved
        assert result["data"][CONF_INVERT_GRID_POWER_SIGN] is True
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-001"

    def test_rescan_preserves_invert_false(self) -> None:
        """Existing entry with invert=False must keep False after rescan."""
        e3dc_entry = _make_e3dc_entry()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "S10E-12345",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            },
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {"entry_id": "uem-001"}
        flow.handler = DOMAIN

        all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: [e3dc_entry]}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        def _mock_discover(_self, _entry_id):
            return full_map

        with patch.object(UemConfigFlow, "_discover_entities", _mock_discover):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        assert result["data"][CONF_INVERT_GRID_POWER_SIGN] is False

    def test_fill_blank_fields_does_not_overwrite_invert(self) -> None:
        """_fill_blank_fields must not overwrite CONF_INVERT_GRID_POWER_SIGN."""
        flow = UemConfigFlow()
        e3dc_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )
        current_data = {
            CONF_INVERT_GRID_POWER_SIGN: True,
            CONF_SOC_ENTITY: "",
            CONF_PV_POWER_ENTITY: "",
            CONF_HOUSE_POWER_ENTITY: "",
            CONF_GRID_EXPORT_ENTITY: "",
            CONF_BATTERY_CHARGE_ENTITY: "",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
        }

        result = flow._fill_blank_fields(e3dc_map, current_data)

        # Mapping fields get discovery values
        assert result[CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        # Invert flag must be preserved (not overwritten)
        assert result[CONF_INVERT_GRID_POWER_SIGN] is True
