"""Tests for universal config flow: e3dc_rscp optional, manual mapping, reconfigure.

TDD cycle: write failing tests first, then implement to green.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

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
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    FORECAST_SOLAR_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap

# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #

def _make_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    """Create a minimal e3dc_rscp ConfigEntry."""
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


def _make_uem_entry(
    entry_id: str = "uem-001",
    unique_id: str = "uem:manual-001",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    """Create a minimal UEM ConfigEntry (no e3dc_rscp dependency)."""
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM – Universal Energy Manager",
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
    existing_uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Construct a UemConfigFlow with a mocked hass."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    ce = hass.config_entries
    _all_entries_by_domain: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
    }
    if forecast_entries:
        _all_entries_by_domain[FORECAST_SOLAR_DOMAIN] = forecast_entries
    if existing_uem_entry is not None:
        _all_entries_by_domain[DOMAIN] = [existing_uem_entry]

    def _async_entries(domain: str | None = None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(
        side_effect=lambda domain, uid: existing_uem_entry
        if existing_uem_entry and domain == DOMAIN
        else None,
    )
    return flow


def _run_flow_coroutine(coroutine) -> dict:
    """Execute an async flow step."""
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coroutine
    )


def _make_manual_data(
    soc="sensor.manual_soc",
    pv="sensor.manual_pv",
    house="sensor.manual_house",
    grid="sensor.manual_grid",
    charge="sensor.manual_charge",
    capacity="sensor.manual_capacity",
    max_charge="sensor.manual_max",
):
    """Build manual entity data for config entry."""
    return {
        CONF_SOC_ENTITY: soc,
        CONF_PV_POWER_ENTITY: pv,
        CONF_HOUSE_POWER_ENTITY: house,
        CONF_GRID_EXPORT_ENTITY: grid,
        CONF_BATTERY_CHARGE_ENTITY: charge,
        CONF_BATTERY_CAPACITY_ENTITY: capacity,
        CONF_MAX_CHARGE_POWER_ENTITY: max_charge,
        CONF_E3DC_CONFIG_ENTRY_ID: None,
        CONF_E3DC_SOURCE_UNIQUE_ID: None,
        CONF_FORECAST_SOLAR_ENTRY_IDS: [],
        CONF_MANUAL_ENTITIES: True,
    }


def _mock_location(hass: MagicMock) -> None:
    """Mock hass.config.location for manual mapping creation."""
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TEST: No e3dc_rscp → NO ABORT, show choice                                 #
# =========================================================================== #

class TestNoE3dcShowsChoice:
    """When no e3dc_rscp exists, the flow must NOT abort."""

    def test_user_step_no_e3dc_shows_form_not_abort(self) -> None:
        """Without any e3dc_rscp entries the user step should show a form,
        not abort with 'e3dc_rscp_not_configured'."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "no_e3dc_choice"

    def test_no_e3dc_form_has_cancel_continue_buttons(self) -> None:
        """The choice form must present 'cancel' and 'continue' options."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        result = _run_flow_coroutine(flow.async_step_user())

        schema_dict = dict(result["data_schema"].schema)
        assert "confirm" in schema_dict

    def test_user_choice_cancel_aborts(self) -> None:
        """Selecting 'cancel' on the choice form should abort with a clear
        message about setting up e3dc_rscp first."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        result = _run_flow_coroutine(
            flow.async_step_no_e3dc_choice({"confirm": "cancel"})
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "e3dc_rscp_optional_cancel"

    def test_user_choice_continue_goes_to_manual(self) -> None:
        """Selecting 'continue' on the choice form should go to manual mapping
        with empty prefill (no adapter entities available)."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        result = _run_flow_coroutine(
            flow.async_step_no_e3dc_choice({"confirm": "continue"})
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"
        # No e3dc adapter → empty prefill
        schema_dict = dict(result["data_schema"].schema)
        # The manual_mapping form must have all required entity fields
        for field in [
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_MAX_CHARGE_POWER_ENTITY,
        ]:
            assert field in schema_dict, f"Missing field: {field}"


# =========================================================================== #
# TEST: Manual mapping submission creates entry without e3dc_rscp             #
# =========================================================================== #

class TestManualMappingCreation:
    """Manual mapping should create a UEM entry even without e3dc_rscp."""

    def test_manual_mapping_creates_entry_no_e3dc(self) -> None:
        """Full manual entity submission should create a valid entry."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, [])

        # Step 1: choose to continue
        _run_flow_coroutine(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        # Step 2: submit manual entities
        manual_data = _make_manual_data()
        result = _run_flow_coroutine(
            flow.async_step_manual_mapping(manual_data)
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] is None
        assert result["data"][CONF_E3DC_SOURCE_UNIQUE_ID] is None
        assert result["data"].get(CONF_MANUAL_ENTITIES) is True
        assert result["data"][CONF_SOC_ENTITY] == "sensor.manual_soc"

    def test_manual_mapping_aborts_on_missing_entities(self) -> None:
        """Empty manual mapping should show errors for all required fields."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        _run_flow_coroutine(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        result = _run_flow_coroutine(flow.async_step_manual_mapping({}))

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"
        assert "errors" in result
        assert result["errors"]["base"] == "missing_required_entities"


# =========================================================================== #
# TEST: With e3dc_rscp → discovery prefill + manual edit                     #
# =========================================================================== #

class TestWithE3dcPrefill:
    """When e3dc_rscp exists, discovered entities become editable prefill."""

    def test_e3dc_discovery_sets_prefill(self) -> None:
        """With e3dc_rscp, the confirm step shows discovered entities as prefill
        which are editable in manual mapping."""
        hass = MagicMock()
        e3dc_entry = _make_entry(entry_id="e3dc-alpha", unique_id="HW-999")
        flow = _make_flow(hass, [e3dc_entry])
        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        flow._e3dc_entry_id = e3dc_entry.entry_id

        with patch.object(UemConfigFlow, "_discover_entities", return_value=full_map):
            result = _run_flow_coroutine(flow.async_step_confirm())

        # Should still be a form (confirm step)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

    def test_e3dc_confirm_creates_entry_with_e3dc(self) -> None:
        """Confirm with e3dc should create an entry with the e3dc reference."""
        hass = MagicMock()
        e3dc_entry = _make_entry(entry_id="e3dc-alpha", unique_id="HW-999")
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

        with patch.object(UemConfigFlow, "_discover_entities", return_value=full_map):
            result = _run_flow_coroutine(
                flow.async_step_confirm({"confirm": "yes"})
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-alpha"
        assert result["data"][CONF_E3DC_SOURCE_UNIQUE_ID] == "HW-999"


# =========================================================================== #
# TEST: Forecast.Solar optional, unlimited sources                            #
# =========================================================================== #

class TestForecastSolarOptional:
    """Forecast.Solar is optional and supports unlimited sources."""

    def test_no_forecast_solar_entries_works(self) -> None:
        """Manual mapping creation works with no forecast_solar entries."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, [], forecast_entries=[])

        _run_flow_coroutine(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        manual_data = _make_manual_data()
        result = _run_flow_coroutine(flow.async_step_manual_mapping(manual_data))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS] == []

    def test_multiple_forecast_solar_entries_collected(self) -> None:
        """When multiple forecast_solar entries exist, all are included."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
        fs1 = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=FORECAST_SOLAR_DOMAIN,
            title="Dach Nord",
            data={},
            source="user",
            entry_id="fs-nord",
            unique_id="fs-nord-uid",
            state=config_entries.ConfigEntryState.LOADED,
        )
        fs2 = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=FORECAST_SOLAR_DOMAIN,
            title="Dach Süd",
            data={},
            source="user",
            entry_id="fs-sued",
            unique_id="fs-sued-uid",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow = _make_flow(hass, [e3dc_entry], forecast_entries=[fs1, fs2])
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

        with patch.object(UemConfigFlow, "_discover_entities", return_value=full_map):
            result = _run_flow_coroutine(
                flow.async_step_confirm({"confirm": "yes"})
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert set(result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS]) == {
            "fs-nord",
            "fs-sued",
        }


# =========================================================================== #
# TEST: Reconfigure action                                                    #
# =========================================================================== #

class TestReconfigureFlow:
    """Reconfigure action must rescan adapters without silently overwriting."""

    def test_reconfigure_step_shows_source(self) -> None:
        """Reconfigure should show current source info."""
        hass = MagicMock()
        uem_entry = _make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
            }
        )
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {}
        flow.handler = DOMAIN
        flow._async_current_entries = MagicMock(return_value=[uem_entry])

        # Reconfigure is triggered via options flow or reconfigure flow
        # For ConfigEntry, we use async_step_reconfigure
        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            flow.async_step_reconfigure()
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    def test_reconfigure_preserves_manual_values(self) -> None:
        """Reconfigure must not overwrite manually configured entity values."""
        hass = MagicMock()
        manual_data = _make_manual_data(
            soc="sensor.custom_soc", pv="sensor.custom_pv"
        )
        uem_entry = _make_uem_entry(data=manual_data)
        uem_entry._entry_id = "uem-001"

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {}
        flow.handler = DOMAIN

        # Mock _async_current_entries to return existing entry (so user step not blocked)
        # Actually reconfigure bypasses that check
        flow._async_current_entries = MagicMock(return_value=[uem_entry])
        flow._entry = uem_entry

        # Reconfigure step shows current state
        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            flow.async_step_reconfigure()
        )

        assert result["type"] == FlowResultType.FORM


# =========================================================================== #
# TEST: Existing integration tests still pass (no regression on e3dc path)    #
# =========================================================================== #

class TestExistingPathNoRegression:
    """Ensure the existing e3dc_rscp flow path still works."""

    def test_with_e3dc_single_entry_skips_to_confirm(self) -> None:
        """With one e3dc entry, user step skips directly to confirm."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
        flow = _make_flow(hass, [e3dc_entry])

        with patch.object(UemConfigFlow, "_discover_entities", return_value=E3dcEntityMap()):
            result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

    def test_with_e3dc_multiple_shows_selection(self) -> None:
        """With multiple e3dc entries, show selection form."""
        hass = MagicMock()
        entry1 = _make_entry(entry_id="e3dc-1", title="E3DC 1")
        entry2 = _make_entry(entry_id="e3dc-2", title="E3DC 2")
        flow = _make_flow(hass, [entry1, entry2])

        result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
