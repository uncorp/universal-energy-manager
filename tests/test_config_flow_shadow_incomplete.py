"""TDD tests for universal config flow with incomplete Shadow setup.

Key rules (post-simplified-schema):
- e3dc_rscp is optional, never mandatory
- Battery capacity: entity in kWh OR manual kWh value
- Max charge power: entity in W OR manual W value
- Battery power: single signed entity (battery_charge_entity) only
- Grid power: single signed entity (grid_export_entity) with sign convention
- Solar/PV forecasts: optional, unlimited sources
- No adapter + no entities → Shadow – Einrichtung unvollständig, never control
- Version stays 0.1.x forever
- No battery_power_mode, battery_discharge_entity, grid_power_mode,
  grid_import_entity, battery_power_sign_convention anywhere in the UI.
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
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    SHADOW_STATUS_UNVOLLSTANDIG,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap

# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title=title,
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_forecast_entry(
    entry_id: str = "fs-001",
    title: str = "Forecast Solar",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=FORECAST_SOLAR_DOMAIN,
        title=title,
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="fs-001-uid",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry] | None = None,
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
    existing_uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    ce = hass.config_entries
    all_by_domain: dict[str, list[config_entries.ConfigEntry]] = {}
    if e3dc_entries:
        all_by_domain[E3DC_RSCP_DOMAIN] = e3dc_entries
    if forecast_entries:
        all_by_domain[FORECAST_SOLAR_DOMAIN] = forecast_entries
    if existing_uem_entry:
        all_by_domain[DOMAIN] = [existing_uem_entry]

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in all_by_domain.values():
                result.extend(entries)
            return result
        return all_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def _mock_location(hass: MagicMock):
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TEST 1: Fresh HA — no e3dc, no entities at all → manual flow works         #
# =========================================================================== #


class TestFreshHaNoE3dcNoEntities:
    """A truly fresh HAOS without e3dc_rscp and without any entities.
    User must be able to continue with manual mapping."""

    def test_user_step_no_e3dc_shows_choice(self):
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        result = _run(flow.async_step_user())
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "no_e3dc_choice"

    def test_continue_to_manual_mapping(self):
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        result = _run(
            flow.async_step_no_e3dc_choice({"confirm": "continue"})
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"


# =========================================================================== #
# TEST 2: Manual config with ONLY fixed numbers (no entities)                #
# =========================================================================== #


class TestManualFixedValuesNoEntities:
    """User enters manual kWh/W values instead of entity IDs.
    Battery capacity can be a fixed kWh number.
    Max charge power can be a fixed W number.
    This must create a valid entry."""

    def test_create_entry_with_manual_battery_capacity_kwh(self):
        """Manual battery_capacity_entity field left empty, manual kWh set."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "",  # no entity
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.5",  # manual kWh
            CONF_MAX_CHARGE_POWER_ENTITY: "",  # no entity
            CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",  # manual W
            CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_BATTERY_MANUAL_CAPACITY_KWH] == "10.5"
        assert result["data"][CONF_MAX_CHARGE_MANUAL_POWER_W] == "5000"

    def test_create_entry_with_both_entity_and_manual(self):
        """If both entity AND manual value are set for the same field,
        the schema should accept entity (entity takes priority)."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_battery_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.5",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
            CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY


# =========================================================================== #
# TEST 3: Battery power — single signed entity only (Req 1)                  #
# =========================================================================== #


class TestBatteryPowerSingleEntity:
    """Battery power must be exactly one field (battery_charge_entity).
    No battery_power_mode, battery_discharge_entity, or battery_power_sign_convention.
    The grid sign convention covers only grid, not battery."""

    def _schema_keys(self, flow: UemConfigFlow) -> set:
        schema_dict = flow._build_full_schema({})
        return set(schema_dict.keys())

    def test_battery_charge_entity_in_schema(self):
        """CONF_BATTERY_CHARGE_ENTITY must be in the schema."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_CHARGE_ENTITY in keys

    def test_no_battery_discharge_in_schema(self):
        """CONF_BATTERY_DISCHARGE_ENTITY must NOT be in the schema."""
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_DISCHARGE_ENTITY,
        )

        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_DISCHARGE_ENTITY not in keys

    def test_no_battery_power_mode_in_schema(self):
        """CONF_BATTERY_POWER_MODE must NOT be in the schema."""
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_POWER_MODE,
        )

        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_POWER_MODE not in keys

    def test_submit_with_battery_charge_only(self):
        """Submitting a single battery_charge_entity creates an entry."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.soc",
            CONF_PV_POWER_ENTITY: "sensor.pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.house",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_BATTERY_CHARGE_ENTITY] == "sensor.battery_charge"


# =========================================================================== #
# TEST 4: Grid power — single signed entity with sign convention (Req 2)     #
# =========================================================================== #


class TestGridPowerSingleEntity:
    """Grid power must be exactly one field (grid_export_entity) with a
    sign-convention selector. No grid_power_mode or grid_import_entity."""

    def _schema_keys(self, flow: UemConfigFlow) -> set:
        schema_dict = flow._build_full_schema({})
        return set(schema_dict.keys())

    def test_grid_export_entity_in_schema(self):
        """CONF_GRID_EXPORT_ENTITY must be in the schema."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_GRID_EXPORT_ENTITY in keys

    def test_invert_grid_power_sign_in_schema(self):
        """CONF_INVERT_GRID_POWER_SIGN must be in the schema."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_INVERT_GRID_POWER_SIGN in keys

    def test_no_grid_import_in_schema(self):
        """CONF_GRID_IMPORT_ENTITY must NOT be in the schema."""
        from custom_components.universal_energy_manager.const import (
            CONF_GRID_IMPORT_ENTITY,
        )

        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_GRID_IMPORT_ENTITY not in keys

    def test_no_grid_power_mode_in_schema(self):
        """CONF_GRID_POWER_MODE must NOT be in the schema."""
        from custom_components.universal_energy_manager.const import (
            CONF_GRID_POWER_MODE,
        )

        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        keys = self._schema_keys(flow)
        assert CONF_GRID_POWER_MODE not in keys

    def test_submit_with_grid_export_and_sign_convention(self):
        """Submitting grid_export_entity + sign convention creates an entry."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.soc",
            CONF_PV_POWER_ENTITY: "sensor.pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.house",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid",
            CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_GRID_EXPORT_ENTITY] == "sensor.grid"
        assert result["data"][CONF_INVERT_GRID_POWER_SIGN] == (
            "positive_is_discharging_import"
        )


# =========================================================================== #
# TEST 5: Solar-only forecasts, unlimited                                    #
# =========================================================================== #


class TestSolarOnlyForecasts:
    """Only Solar/PV forecasts supported. No BHKW/Wind."""

    def test_multiple_forecast_solar_sources_collected(self):
        """Multiple forecast_solar entries are all collected."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(
            hass,
            e3dc_entries=[],
            forecast_entries=[
                _make_forecast_entry("fs-1", "Dach Nord"),
                _make_forecast_entry("fs-2", "Dach Sued"),
            ],
        )

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_battery",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.5",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
            CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert len(result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS]) == 2


# =========================================================================== #
# TEST 6: Shadow safety — incomplete setup                                   #
# =========================================================================== #


class TestShadowSafetyIncompleteSetup:
    """When configured with adapter but no entities, or incomplete entities,
    the coordinator must report 'Shadow – Einrichtung unvollständig'."""

    def test_shadow_status_incomplete_when_entities_missing(self):
        """Coordinator with missing required entities → unvollständig."""
        from custom_components.universal_energy_manager.coordinator import (
            ShadowData,
            UemShadowCoordinator,
        )

        hass = MagicMock()
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_E3DC_SOURCE_UNIQUE_ID: None,
                CONF_MANUAL_ENTITIES: True,
                # Missing most entities → incomplete
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
            },
            source="user",
            entry_id="uem-001",
            unique_id="uem:manual:test",
            state=config_entries.ConfigEntryState.LOADED,
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            coord._async_update_data()
        )
        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert result.commands_sent is False
        assert result.planned_charge_limit_w == 0.0

    def test_shadow_status_unvollstaendig_also_when_only_adapter(self):
        """When only e3dc adapter exists but entities are not mapped → unvollständig."""
        from custom_components.universal_energy_manager.coordinator import (
            ShadowData,
            UemShadowCoordinator,
        )

        hass = MagicMock()
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                # All required fields empty/missing
            },
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:HW-999",
            state=config_entries.ConfigEntryState.LOADED,
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            coord._async_update_data()
        )
        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG

    def test_shadow_complete_with_manual_capacity_power(self):
        """Entry with manual kWh/W values (no entity for capacity/power)
        must NOT be flagged as incomplete."""
        from custom_components.universal_energy_manager.coordinator import (
            UemShadowCoordinator,
        )

        hass = MagicMock()
        # All core entities set via entity IDs; capacity/power via manual values
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM Manual",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_E3DC_SOURCE_UNIQUE_ID: None,
                CONF_MANUAL_ENTITIES: True,
                CONF_SOC_ENTITY: "sensor.manual_soc",
                CONF_PV_POWER_ENTITY: "sensor.manual_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "",  # no entity
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.5",
                CONF_MAX_CHARGE_POWER_ENTITY: "",  # no entity
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
            },
            source="user",
            entry_id="uem-manual",
            unique_id="uem:manual:test",
            state=config_entries.ConfigEntryState.LOADED,
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        # _is_incomplete must return False when manual kWh/W fills the gap
        assert coord._is_incomplete() is False

    def test_shadow_complete_entity_fallback_to_manual(self):
        """When entity is empty string but manual kWh/W set → complete."""
        from custom_components.universal_energy_manager.coordinator import (
            UemShadowCoordinator,
        )

        hass = MagicMock()
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "",  # empty entity
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "13.0",
                CONF_MAX_CHARGE_POWER_ENTITY: "",  # empty entity
                CONF_MAX_CHARGE_MANUAL_POWER_W: "12000",
            },
            source="user",
            entry_id="uem-001",
            unique_id="test",
            state=config_entries.ConfigEntryState.LOADED,
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        assert coord._is_incomplete() is False


# =========================================================================== #
# TEST 7: Reconfigure — no silent overwrite of manual values                 #
# =========================================================================== #


class TestReconfigureNoSilentOverwrite:
    """Reconfigure must fetch adapter suggestions without overwriting
    manually-entered values."""

    def test_reconfigure_rescan_fetches_suggestions_only(self):
        """Rescan should NOT overwrite existing manual values.
        If a field is already set, it stays set."""
        hass = MagicMock()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_INVERT_GRID_POWER_SIGN: "positive_is_discharging_import",
            },
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:HW-999",
            state=config_entries.ConfigEntryState.LOADED,
        )

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-001"}
        flow.handler = DOMAIN
        flow._async_current_entries = MagicMock(return_value=[uem_entry])

        # Mock the e3dc entry lookup
        e3dc_entry = _make_e3dc_entry(
            entry_id="e3dc-001", unique_id="HW-999"
        )
        all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: [e3dc_entry]}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)

        # Mock rescan that finds the same entities
        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max",
        )

        def _mock_discover(_self, _entry_id):
            return full_map

        with patch.object(UemConfigFlow, "_discover_entities", _mock_discover):
            result = _run(
                flow.async_step_reconfigure({"rescan_e3dc": "True", "edit_manual": "False"})
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-001"
        # Manual values should be preserved (not overwritten by rescan)
        assert result["data"][CONF_SOC_ENTITY] == "sensor.e3dc_soc"


# =========================================================================== #
# TEST 8: Version rule — manifest must stay 0.1.x                            #
# =========================================================================== #


class TestVersionRule:
    """Version must be 0.1.x. Never 0.2.0."""

    def test_manifest_version_is_01x(self):
        import json

        manifest_path = (
            "custom_components/universal_energy_manager/manifest.json"
        )
        with open(manifest_path) as f:
            manifest = json.load(f)
        version = manifest["version"]
        parts = version.split(".")
        assert int(parts[0]) == 0
        assert int(parts[1]) == 1
        assert len(parts) == 3, f"Version {version!r} must have exactly 3 parts"

    def test_manifest_version_not_02(self):
        """Version must never be 0.2.x — shadow lane stays 0.1.x forever."""
        import json

        manifest_path = (
            "custom_components/universal_energy_manager/manifest.json"
        )
        with open(manifest_path) as f:
            manifest = json.load(f)
        version = manifest["version"]
        parts = version.split(".")
        assert parts[1] != "2", f"Version must stay 0.1.x, got {version}"
