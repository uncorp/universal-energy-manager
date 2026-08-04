"""TDD tests for UEM Task B: Multi-Quelle/Multi-Akku — Generator data flow.

Slice 2: Verifying that the generator JSON string round-trips correctly
through reconfigure_edit.  Each generator dict has:
  - generator_name (str)
  - generator_power_entity (str, entity ID)

The existing test (slice 1) already verified that the schema includes
CONF_GENERATORS.  This slice verifies:
  1. Empty list → empty JSON → persisted as empty list on reload.
  2. One generator → correct JSON → persisted and retrievable.
  3. Two generators → correct JSON → both present after reconfigure.
  4. Existing single generator (from initial install) is preserved.
  5. Submitting an invalid JSON string (malformed) → treated as empty
     (defensive parsing, never crashes the config flow).
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GENERATOR_NAME,
    CONF_GENERATOR_POWER_ENTITY,
    CONF_GENERATORS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    FORECAST_SOLAR_DOMAIN,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
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


def _make_forecast_solar_entry(
    entry_id: str = "forecast-solar-001",
    title: str = "Forecast.Solar",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=FORECAST_SOLAR_DOMAIN,
        title=title,
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="forecast-solar:test",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_uem_entry(
    entry_id: str = "uem-001",
    unique_id: str = "e3dc_rscp:HW-12345",
    data: dict | None = None,
    title: str = "UEM – Universal Energy Manager",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=title,
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow_with_all(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry] | None = None,
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
    uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Build a UemConfigFlow with mocked async_entries for all domains."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries or [],
        FORECAST_SOLAR_DOMAIN: forecast_entries or [],
    }
    if uem_entry:
        _all[DOMAIN] = [uem_entry]

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


def _mock_location(hass: MagicMock) -> None:
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


def _make_generator(name: str, entity: str) -> dict:
    """Helper to create a generator dict."""
    return {
        CONF_GENERATOR_NAME: name,
        CONF_GENERATOR_POWER_ENTITY: entity,
    }


# =========================================================================== #
# TEST 1: Empty generators list round-trips as empty JSON                     #
# =========================================================================== #


class TestGeneratorsEmptyRoundTrip:
    """Submitting an empty generators list must persist as []."""

    def test_reconfigure_empty_generators(self) -> None:
        """When no generators are configured, reconfigure_edit must save an
        empty list (serialised as '[]')."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-empty-gen",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-empty-gen"}

        # Get the edit form
        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Submit with empty generators JSON string
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_GENERATORS: "[]",
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert saved_data[CONF_GENERATORS] == "[]"


# =========================================================================== #
# TEST 2: Single generator round-trips correctly                              #
# =========================================================================== #


class TestGeneratorsSingleRoundTrip:
    """Adding one generator must persist with correct JSON."""

    def test_reconfigure_one_generator(self) -> None:
        """A single additional generator (BHKW) must be stored as a JSON
        list containing one generator dict."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-one-gen",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-one-gen"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Add a BHKW generator
        gen = _make_generator("BHKW", "sensor.bhkw_power")
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_GENERATORS: json.dumps([gen], ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        # Verify the JSON string was stored
        assert saved_data[CONF_GENERATORS] == json.dumps([gen], ensure_ascii=False)

        # Verify we can parse it back to a list of dicts
        parsed = json.loads(saved_data[CONF_GENERATORS])
        assert len(parsed) == 1
        assert parsed[0][CONF_GENERATOR_NAME] == "BHKW"
        assert parsed[0][CONF_GENERATOR_POWER_ENTITY] == "sensor.bhkw_power"


# =========================================================================== #
# TEST 3: Two generators round-trip correctly                                 #
# =========================================================================== #


class TestGeneratorsTwoRoundTrip:
    """Adding two generators must persist with correct JSON."""

    def test_reconfigure_two_generators(self) -> None:
        """Two generators (E3DC-PV + BHKW) must both be stored and parsed."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-two-gen",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-two-gen"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # E3DC-PV is the existing generator, BHKW is added
        generators = [
            _make_generator("E3DC-PV", "sensor.e3dc_pv"),
            _make_generator("BHKW", "sensor.bhkw_power"),
        ]
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_GENERATORS: json.dumps(generators, ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        parsed = json.loads(saved_data[CONF_GENERATORS])
        assert len(parsed) == 2
        assert parsed[0][CONF_GENERATOR_NAME] == "E3DC-PV"
        assert parsed[0][CONF_GENERATOR_POWER_ENTITY] == "sensor.e3dc_pv"
        assert parsed[1][CONF_GENERATOR_NAME] == "BHKW"
        assert parsed[1][CONF_GENERATOR_POWER_ENTITY] == "sensor.bhkw_power"


# =========================================================================== #
# TEST 4: Existing single generator (from initial install) is preserved       #
# =========================================================================== #


class TestGeneratorsPreservedFromInstall:
    """A generator stored during initial install must survive reconfigure_edit."""

    def test_reconfigure_preserves_existing_generator(self) -> None:
        """When the UEM entry already has one generator (from initial install),
        reconfigure_edit must preserve it even when the user does not touch the
        generators field."""
        hass = MagicMock()
        _mock_location(hass)

        existing_gen = _make_generator("E3DC-PV", "sensor.e3dc_pv")
        uem_entry = _make_uem_entry(
            entry_id="uem-preserve-gen",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
                CONF_GENERATORS: json.dumps([existing_gen], ensure_ascii=False),
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-preserve-gen"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Submit without changing generators (should preserve the existing one)
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_GENERATORS: json.dumps([existing_gen], ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        parsed = json.loads(saved_data[CONF_GENERATORS])
        assert len(parsed) == 1
        assert parsed[0][CONF_GENERATOR_NAME] == "E3DC-PV"


# =========================================================================== #
# TEST 5: Malformed JSON string → treated as empty (defensive)                #
# =========================================================================== #


class TestGeneratorsMalformedJson:
    """Malformed JSON in the generators field must not crash the config flow."""

    def test_reconfigure_malformed_generators_json(self) -> None:
        """When the user submits a malformed JSON string for generators,
        the config flow must treat it as an empty list (defensive parsing)
        and not raise an exception."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-bad-json",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-bad-json"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Submit with malformed JSON — must not crash
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_GENERATORS: "{invalid json",
            })
        )

        # The flow should complete (not crash) — either as ABORT or FORM
        # The key assertion is that no exception was raised
        assert result["type"] in (FlowResultType.ABORT, FlowResultType.FORM), (
            f"Expected ABORT or FORM, got {result['type']} — malformed JSON "
            f"should not crash the config flow"
        )
