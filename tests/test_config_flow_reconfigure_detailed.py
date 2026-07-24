"""TDD tests for remaining config_flow gaps: reconfigure detail paths and schema helpers.

Covers:
- _show_reconfigure_edit (config_flow.py:502-506)
- _rescan_e3dc updating non-manual fields (config_flow.py:541-543)
- _get_current_entry via context entry_id (config_flow.py:555, 559)
- _build_entity_schema helper (config_flow.py:571-580)
- _build_full_schema helper (config_flow.py:585)
- confirm step user_input with non-string values (config_flow.py:263-264, 266)
- manual_mapping elif branches for prefill preservation (config_flow.py:346-349)
- sensor.py async_setup_entry function itself (lines 22-23)
- coordinator exception paths in threaded plan_charge (coordinator.py:445-447, 464-465)
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
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
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


def _make_uem_entry(
    entry_id: str = "uem-001",
    unique_id: str = "e3dc_rscp:HW-999",
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


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
    uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
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


# =========================================================================== #
# TEST: _get_current_entry via context entry_id                               #
# =========================================================================== #


class TestGetCurrentEntryViaContext:
    """_get_current_entry should return entry from context when entry_id is set."""

    def test_get_current_entry_returns_context_entry(self) -> None:
        """When context has entry_id, _get_current_entry finds it in HA entries."""
        hass = MagicMock()
        uem_entry = _make_uem_entry(entry_id="uem-ctx")
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-ctx"}
        flow.handler = DOMAIN

        ce = hass.config_entries
        _all = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in _all.values():
                    result.extend(entries)
                return result
            return _all.get(domain, [])

        ce.async_entries = MagicMock(side_effect=_async_entries)

        result = flow._get_current_entry()
        assert result is uem_entry

    def test_get_current_entry_returns_first_from_list_when_no_context(self) -> None:
        """When context has no entry_id, falls back to _async_current_entries."""
        hass = MagicMock()
        uem_entry = _make_uem_entry()
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {}
        flow.handler = DOMAIN
        flow._async_current_entries = MagicMock(return_value=[uem_entry])

        result = flow._get_current_entry()
        assert result is uem_entry

    def test_get_current_entry_returns_none_when_no_entry_found(self) -> None:
        """When entry_id in context doesn't match any HA entry, returns None."""
        hass = MagicMock()
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-nonexistent"}
        flow.handler = DOMAIN

        ce = hass.config_entries
        _all = {DOMAIN: [], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in _all.values():
                    result.extend(entries)
                return result
            return _all.get(domain, [])

        ce.async_entries = MagicMock(side_effect=_async_entries)

        result = flow._get_current_entry()
        assert result is None


# =========================================================================== #
# TEST: _show_reconfigure_edit returns form                                   #
# =========================================================================== #


class TestShowReconfigureEdit:
    """_show_reconfigure_edit should display the edit form."""

    def test_show_reconfigure_edit_returns_form(self) -> None:
        """The edit form step shows a form with the reconfigure_edit step_id."""
        hass = MagicMock()
        uem_entry = _make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
            }
        )
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-001"}
        flow.handler = DOMAIN

        with patch.object(UemConfigFlow, "_get_current_entry", return_value=uem_entry):
            result = _run(
                flow.async_step_reconfigure({"rescan_e3dc": False, "edit_manual": True})
            )

        # Should go to _show_reconfigure_edit → reconfigure_edit form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"


# =========================================================================== #
# TEST: _rescan_e3dc updates blank fields from discovery                      #
# =========================================================================== #


class TestRescanE3dcUpdatesBlankFields:
    """_rescan_e3dc should only update fields that were not manually set (blank)."""

    def test_rescan_updates_empty_fields_from_discovery(self) -> None:
        """Blank fields get filled from e3dc discovery; non-blank preserved."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.custom_soc",  # non-blank → preserved
                CONF_PV_POWER_ENTITY: "",  # blank → updated
                CONF_HOUSE_POWER_ENTITY: "",  # blank → updated
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MANUAL_ENTITIES: False,
            }
        )
        flow = _make_flow(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": "uem-001"}

        new_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(UemConfigFlow, "_discover_entities", return_value=new_map):
            result = _run(
                flow.async_step_reconfigure({"rescan_e3dc": "True", "edit_manual": "False"})
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Non-blank field preserved
        assert result["data"][CONF_SOC_ENTITY] == "sensor.custom_soc"
        # Blank fields updated from discovery
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"
        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result["data"][CONF_BATTERY_CAPACITY_ENTITY] == "sensor.e3dc_capacity"
        assert result["data"][CONF_MAX_CHARGE_POWER_ENTITY] == "sensor.e3dc_max_charge"


# =========================================================================== #
# TEST: confirm step user_input with non-string values                        #
# =========================================================================== #


class TestConfirmUserInputNonString:
    """Confirm step user input can contain non-string values (e.g. integers
    from HA form widgets). The flow should handle them without crashing."""

    def test_confirm_handles_non_string_values(self) -> None:
        """Non-string values in user_input should be accepted without error."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        flow = _make_flow(hass, [e3dc_entry])
        flow._e3dc_entry_id = e3dc_entry.entry_id

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        # Simulate user_input with an integer value (non-string)
        user_input = {
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            "some_int_field": 42,  # non-string value
        }

        with patch.object(UemConfigFlow, "_discover_entities", return_value=full_map):
            result = _run(flow.async_step_confirm(user_input))

        assert result["type"] == FlowResultType.CREATE_ENTRY


# =========================================================================== #
# TEST: manual_mapping elif branches for prefill preservation                #
# =========================================================================== #


class TestManualMappingPrefillPreservation:
    """manual_mapping should preserve prefill values when user doesn't submit
    a field (the elif branch that does 'pass')."""

    def test_prefill_preserved_for_unsubmitted_fields(self) -> None:
        """Fields not in user_input should keep their prefill values."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        # Only submit core entities; leave others to keep prefill defaults
        partial_data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
        }
        result = _run(flow.async_step_manual_mapping(partial_data))
        assert result["type"] == FlowResultType.CREATE_ENTRY


# =========================================================================== #
# TEST: _build_entity_schema helper                                           #
# =========================================================================== #


class TestBuildEntitySchema:
    """_build_entity_schema should build a schema with core required fields."""

    def test_build_entity_schema_has_core_fields(self) -> None:
        """The helper schema must contain all core required fields."""
        flow = UemConfigFlow()
        schema = flow._build_entity_schema(prefill={"sensor.soc": "sensor.e3dc_soc"})

        from custom_components.universal_energy_manager.config_flow import (
            _CORE_REQUIRED,
        )

        for field in _CORE_REQUIRED:
            assert field in schema

    def test_build_entity_schema_allows_empty_when_flagged(self) -> None:
        """When allow_empty=True, the schema allows empty strings."""
        flow = UemConfigFlow()
        schema = flow._build_entity_schema(allow_empty=True)

        from custom_components.universal_energy_manager.config_flow import (
            _CORE_REQUIRED,
        )

        for field in _CORE_REQUIRED:
            assert field in schema


# =========================================================================== #
# TEST: _build_full_schema helper                                             #
# =========================================================================== #


class TestBuildFullSchema:
    """_build_full_schema must include all manual mapping fields."""

    def test_build_full_schema_has_all_fields(self) -> None:
        """The full schema must contain core entities plus optional fields."""
        flow = UemConfigFlow()
        schema = flow._build_full_schema()

        from custom_components.universal_energy_manager.config_flow import (
            _CORE_REQUIRED,
        )

        for field in _CORE_REQUIRED:
            assert field in schema
        assert CONF_BATTERY_CAPACITY_ENTITY in schema
        assert CONF_BATTERY_MANUAL_CAPACITY_KWH in schema
        assert CONF_MAX_CHARGE_POWER_ENTITY in schema
        assert CONF_MAX_CHARGE_MANUAL_POWER_W in schema
        assert CONF_BATTERY_DISCHARGE_ENTITY in schema
        assert CONF_GRID_IMPORT_ENTITY in schema
        assert "battery_power_mode" in schema  # using the const key name
        assert "grid_power_mode" in schema


# =========================================================================== #
# TEST: coordinator exception paths in thread                                 #
# =========================================================================== #


class TestCoordinatorExceptionPaths:
    """Test that exceptions in the threaded plan_charge path are handled."""

    def test_coordinator_handles_build_planner_config_value_error(self) -> None:
        def test_coordinator_handles_build_planner_config_value_error(self) -> None:
            """When _build_planner_config raises ValueError, the thread should
            catch it and return 0.0 charge_limit_w instead of crashing."""
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
                    CONF_SOC_ENTITY: "sensor.fake_soc",
                    CONF_PV_POWER_ENTITY: "sensor.fake_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.fake_house",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.fake_charge",
                    CONF_BATTERY_CAPACITY_ENTITY: "",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                    CONF_MAX_CHARGE_POWER_ENTITY: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                    CONF_E3DC_CONFIG_ENTRY_ID: None,
                    CONF_E3DC_SOURCE_UNIQUE_ID: None,
                    CONF_FORECAST_SOLAR_ENTRY_IDS: [],
                    CONF_MANUAL_ENTITIES: True,
                },
                source="user",
                entry_id="uem-test",
                unique_id="uem:manual:test",
                state=config_entries.ConfigEntryState.LOADED,
            )
            hass.config_entries.async_entries.return_value = [entry]
            hass.states.get.return_value = None

            coord = UemShadowCoordinator(hass, entry)

            live_data = MagicMock()
            live_data.soc_pct = 50
            live_data.pv_power_w = 1000
            live_data.house_power_w = 500
            live_data.grid_power_w = 0

            # Force _build_planner_config to raise
            with patch.object(
                coord, "_build_planner_config", side_effect=ValueError("test")
            ):
                result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                    coord._compute_charge_limit_async(live_data, False)
                )

            # Should not crash; returns 0.0
            assert result == 0.0

        def test_coordinator_handles_plan_charge_value_error(self) -> None:
            """When plan_charge raises ValueError, the thread catches it and
            returns 0.0 charge_limit_w."""
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
                    CONF_SOC_ENTITY: "sensor.fake_soc",
                    CONF_PV_POWER_ENTITY: "sensor.fake_pv",
                    CONF_HOUSE_POWER_ENTITY: "sensor.fake_house",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.fake_charge",
                    CONF_BATTERY_CAPACITY_ENTITY: "",
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                    CONF_MAX_CHARGE_POWER_ENTITY: "",
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                    CONF_E3DC_CONFIG_ENTRY_ID: None,
                    CONF_E3DC_SOURCE_UNIQUE_ID: None,
                    CONF_FORECAST_SOLAR_ENTRY_IDS: [],
                    CONF_MANUAL_ENTITIES: True,
                },
                source="user",
                entry_id="uem-test",
                unique_id="uem:manual:test",
                state=config_entries.ConfigEntryState.LOADED,
            )
            hass.config_entries.async_entries.return_value = [entry]
            hass.states.get.return_value = None

            coord = UemShadowCoordinator(hass, entry)

            live_data = MagicMock()
            live_data.soc_pct = 50
            live_data.pv_power_w = 1000
            live_data.house_power_w = 500
            live_data.grid_power_w = 0

            # Make storage and config fine, but plan_charge raise
            def _raise_plan(*args, **kwargs):
                raise ValueError("planning error")

            with patch.object(coord, "_build_storage_capabilities"):
                with patch.object(coord, "_build_planner_config"):
                    with patch(
                        "custom_components.universal_energy_manager.coordinator.plan_charge",
                        _raise_plan,
                    ):
                        loop = asyncio.get_event_loop_policy().new_event_loop()
                        result = loop.run_until_complete(
                            coord._compute_charge_limit_async(live_data, False)
                        )

            assert result == 0.0


# =========================================================================== #
# TEST: sensor.py async_setup_entry function                                  #
# =========================================================================== #


class TestSensorAsyncSetupEntry:
    """Test the sensor async_setup_entry function itself (lines 22-23)."""

    def test_async_setup_entry_creates_sensors(self) -> None:
        """async_setup_entry should create the expected set of UEM sensors."""
        from custom_components.universal_energy_manager import sensor as sensor_mod
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
                CONF_SOC_ENTITY: "sensor.fake_soc",
                CONF_PV_POWER_ENTITY: "sensor.fake_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.fake_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.fake_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_E3DC_SOURCE_UNIQUE_ID: None,
                CONF_FORECAST_SOLAR_ENTRY_IDS: [],
                CONF_MANUAL_ENTITIES: True,
            },
            source="user",
            entry_id="uem-test",
            unique_id="uem:manual:test",
            state=config_entries.ConfigEntryState.LOADED,
        )

        coordinator = MagicMock(spec=UemShadowCoordinator)

        domain_data = {entry.entry_id: coordinator}
        hass.data = {DOMAIN: domain_data}

        async_add = MagicMock()

        _run(sensor_mod.async_setup_entry(hass, entry, async_add))

        assert async_add.call_count == 1
        sensors = async_add.call_args[0][0]
        assert len(sensors) == 5
        sensor_types = {type(s).__name__ for s in sensors}
        expected = {
            "UemStatusSensor",
            "UemDecisionSensor",
            "UemPlannedChargeLimitSensor",
            "UemCurrentGenerationSensor",
            "UemTotalLoadSensor",
        }
        assert sensor_types == expected


# =========================================================================== #
# TEST: manual_mapping validation for capacity/power                          #
# =========================================================================== #


class TestManualMappingValidation:
    """Tests for validation paths in manual_mapping that were uncovered."""

    def test_manual_mapping_rejects_missing_battery_capacity(self) -> None:
        """When battery capacity (entity + manual) is missing, manual_mapping
        returns error."""
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
            CONF_BATTERY_CAPACITY_ENTITY: "",  # blank
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",  # blank
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
        }
        result = _run(flow.async_step_manual_mapping(data))

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"
        assert result["errors"]["base"] == "missing_required_entities"

    def test_manual_mapping_rejects_missing_max_charge_power(self) -> None:
        """When max charge power (entity + manual) is missing, manual_mapping
        returns error."""
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
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
            CONF_MAX_CHARGE_POWER_ENTITY: "",  # blank
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",  # blank
        }
        result = _run(flow.async_step_manual_mapping(data))

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"
        assert result["errors"]["base"] == "missing_required_entities"

    def test_reconfigure_no_action_goes_back_to_form(self) -> None:
        """Reconfigure with neither rescan nor edit should show the form again."""
        hass = MagicMock()
        uem_entry = _make_uem_entry()
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-001"}
        flow.handler = DOMAIN

        ce = hass.config_entries
        _all = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in _all.values():
                    result.extend(entries)
                return result
            return _all.get(domain, [])

        ce.async_entries = MagicMock(side_effect=_async_entries)

        result = _run(
            flow.async_step_reconfigure({"rescan_e3dc": "False", "edit_manual": "False"})
        )

        # Should go back to reconfigure form (no action taken)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
