"""TDD for UEM Task B: Initial install (confirm step) with multi-generator/multi-battery.

Slice: The confirm step (used when e3dc_rscp is found) must persist multiple
generators and batteries in the entry data, not only during manual_mapping.

Currently the confirm step builds entity_data from a hardcoded dict that does
not include CONF_GENERATORS / CONF_BATTERIES, so they are never saved.

This slice verifies:
  1. Confirm step persists an empty generators/batteries list.
  2. Confirm step with one generator + one additional battery → correct JSON.
  3. Confirm step with multiple generators + multiple batteries → all present.
  4. Confirm step user_input that overrides prefill values also carries
     generators/batteries through to the entry.
"""

from __future__ import annotations

import asyncio
import json
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
    CONF_BATTERIES,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_BATTERY_NAME,
    CONF_BATTERY_SOC_ENTITY,
    CONF_GENERATOR_NAME,
    CONF_GENERATOR_POWER_ENTITY,
    CONF_GENERATORS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_flow(hass, e3dc_entries=None, forecast_entries=None):
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    _all_entries_by_domain = {
        E3DC_RSCP_DOMAIN: e3dc_entries or [],
        FORECAST_SOLAR_DOMAIN: forecast_entries or [],
    }

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
    hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
        return_value=None,
    )
    return flow


def _make_e3dc_entry(entry_id="e3dc-001", unique_id="HW-12345"):
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC RSCP",
        data={},
        source="config_entry",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_e3dc_map():
    m = MagicMock()
    m.soc = "sensor.e3dc_soc"
    m.pv_power = "sensor.e3dc_pv"
    m.house_power = "sensor.e3dc_house"
    m.grid_export = "sensor.e3dc_grid"
    m.battery_charge = "sensor.e3dc_battery"
    m.battery_capacity = "sensor.e3dc_capacity"
    m.max_charge_power = "sensor.e3dc_max_charge"
    return m


def _make_generator(name, entity):
    return {
        CONF_GENERATOR_NAME: name,
        CONF_GENERATOR_POWER_ENTITY: entity,
    }


def _make_battery(name, soc_entity, capacity_kwh, charge_entity, discharge_entity):
    return {
        CONF_BATTERY_NAME: name,
        CONF_BATTERY_SOC_ENTITY: soc_entity,
        CONF_BATTERY_CAPACITY_KWH: capacity_kwh,
        CONF_BATTERY_CHARGE_POWER_ENTITY: charge_entity,
        CONF_BATTERY_DISCHARGE_POWER_ENTITY: discharge_entity,
    }


def _mock_location(hass, lat=52.5200, lon=13.4050):
    loc = MagicMock()
    loc.latitude = lat
    loc.longitude = lon
    hass.config.location = loc


# =========================================================================== #
# TEST 1: Confirm step persists empty generators/batteries list                #
# =========================================================================== #


class TestConfirmStepEmptyGeneratorsBatteries:
    """Confirm step must persist generators=[] and batteries=[] in the entry."""

    def test_confirm_saves_empty_lists(self):
        hass = MagicMock()
        _mock_location(hass)

        e3dc = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc])

        e3dc_map = _make_e3dc_map()

        with patch(
            "custom_components.universal_energy_manager.config_flow.discover_e3dc_entities",
            return_value=e3dc_map,
        ):
            result = _run(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        generators_str = json.dumps([], ensure_ascii=False)
        batteries_str = json.dumps([], ensure_ascii=False)

        result = _run(
            flow.async_step_confirm(
                {
                    CONF_SOC_ENTITY: "sensor.e3dc_soc",
                    CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                    CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery",
                    CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                    CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                    CONF_INVERT_GRID_POWER_SIGN: False,
                    CONF_GENERATORS: generators_str,
                    CONF_BATTERIES: batteries_str,
                },
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_data = result["data"]
        assert entry_data.get(CONF_GENERATORS) == generators_str
        assert entry_data.get(CONF_BATTERIES) == batteries_str


# =========================================================================== #
# TEST 2: Confirm step with one generator + one additional battery             #
# =========================================================================== #


class TestConfirmStepOneGeneratorOneBattery:
    """Confirm step must persist one generator + one additional battery."""

    def test_confirm_saves_one_gen_one_battery(self):
        hass = MagicMock()
        _mock_location(hass)

        e3dc = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc])

        e3dc_map = _make_e3dc_map()

        with patch(
            "custom_components.universal_energy_manager.config_flow.discover_e3dc_entities",
            return_value=e3dc_map,
        ):
            result = _run(flow.async_step_user())

        assert result["step_id"] == "confirm"

        battery = _make_battery(
            name="Wall-Power",
            soc_entity="sensor.wallpower_soc",
            capacity_kwh="10",
            charge_entity="sensor.wallpower_charge",
            discharge_entity="sensor.wallpower_discharge",
        )
        batteries_str = json.dumps([battery], ensure_ascii=False)
        generators_str = json.dumps([], ensure_ascii=False)

        result = _run(
            flow.async_step_confirm(
                {
                    CONF_SOC_ENTITY: "sensor.e3dc_soc",
                    CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                    CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery",
                    CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                    CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                    CONF_INVERT_GRID_POWER_SIGN: False,
                    CONF_GENERATORS: generators_str,
                    CONF_BATTERIES: batteries_str,
                },
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_data = result["data"]
        assert entry_data[CONF_GENERATORS] == generators_str
        parsed = json.loads(entry_data[CONF_BATTERIES])
        assert len(parsed) == 1
        assert parsed[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert parsed[0][CONF_BATTERY_CAPACITY_KWH] == "10"


# =========================================================================== #
# TEST 3: Confirm step with multiple generators + multiple batteries           #
# =========================================================================== #


class TestConfirmStepMultipleGeneratorsBatteries:
    """Confirm step with multiple generators + multiple batteries."""

    def test_confirm_saves_multiple_gen_and_batteries(self):
        hass = MagicMock()
        _mock_location(hass)

        e3dc = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc])

        e3dc_map = _make_e3dc_map()

        with patch(
            "custom_components.universal_energy_manager.config_flow.discover_e3dc_entities",
            return_value=e3dc_map,
        ):
            result = _run(flow.async_step_user())

        assert result["step_id"] == "confirm"

        gen_bhk = _make_generator("BHKW", "sensor.bhkw_power")
        batteries = [
            _make_battery(
                name="Wall-Power",
                soc_entity="sensor.wallpower_soc",
                capacity_kwh="10",
                charge_entity="sensor.wallpower_charge",
                discharge_entity="sensor.wallpower_discharge",
            ),
            _make_battery(
                name="Solar-Battery",
                soc_entity="sensor.solar_battery_soc",
                capacity_kwh="5",
                charge_entity="sensor.solar_battery_charge",
                discharge_entity="sensor.solar_battery_discharge",
            ),
        ]

        gen_str = json.dumps([gen_bhk], ensure_ascii=False)
        bat_str = json.dumps(batteries, ensure_ascii=False)

        result = _run(
            flow.async_step_confirm(
                {
                    CONF_SOC_ENTITY: "sensor.e3dc_soc",
                    CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                    CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery",
                    CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                    CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                    CONF_INVERT_GRID_POWER_SIGN: False,
                    CONF_GENERATORS: gen_str,
                    CONF_BATTERIES: bat_str,
                },
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_data = result["data"]

        # Generator check
        parsed_gens = json.loads(entry_data[CONF_GENERATORS])
        assert len(parsed_gens) == 1
        assert parsed_gens[0][CONF_GENERATOR_NAME] == "BHKW"

        # Battery check
        parsed_bats = json.loads(entry_data[CONF_BATTERIES])
        assert len(parsed_bats) == 2
        assert parsed_bats[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert parsed_bats[1][CONF_BATTERY_NAME] == "Solar-Battery"


# =========================================================================== #
# TEST 4: Confirm step user_input carries generators/batteries through        #
# =========================================================================== #


class TestConfirmStepUserInputCarriesGeneratorsBatteries:
    """User input during confirm must not lose generators/batteries."""

    def test_confirm_user_input_preserves_gen_bat(self):
        hass = MagicMock()
        _mock_location(hass)

        e3dc = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc])

        e3dc_map = _make_e3dc_map()

        with patch(
            "custom_components.universal_energy_manager.config_flow.discover_e3dc_entities",
            return_value=e3dc_map,
        ):
            result = _run(flow.async_step_user())

        assert result["step_id"] == "confirm"

        gen_str = json.dumps([], ensure_ascii=False)
        bat_str = json.dumps([], ensure_ascii=False)

        # User changes SOC entity but keeps generators/batteries empty
        result = _run(
            flow.async_step_confirm(
                {
                    CONF_SOC_ENTITY: "sensor.my_soc",
                    CONF_PV_POWER_ENTITY: "sensor.my_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.my_house",
                    CONF_GRID_EXPORT_ENTITY: "sensor.my_grid",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.my_charge",
                    CONF_BATTERY_CAPACITY_ENTITY: "sensor.my_capacity",
                    CONF_MAX_CHARGE_POWER_ENTITY: "sensor.my_max",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                    CONF_INVERT_GRID_POWER_SIGN: False,
                    CONF_GENERATORS: gen_str,
                    CONF_BATTERIES: bat_str,
                },
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_data = result["data"]
        assert entry_data[CONF_SOC_ENTITY] == "sensor.my_soc"
        assert entry_data[CONF_GENERATORS] == gen_str
        assert entry_data[CONF_BATTERIES] == bat_str
