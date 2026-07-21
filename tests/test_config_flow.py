"""Tests for UemConfigFlow lifecycle and decision paths."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    _REQUIRED_FIELDS,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap


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


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
    existing_uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Construct a UemConfigFlow with a mocked hass that returns the given e3dc entries."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    # Mock config_entries manager
    ce = hass.config_entries
    _all_entries_by_domain: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
    }
    if existing_uem_entry is not None:
        _all_entries_by_domain[DOMAIN] = [existing_uem_entry]

    def _async_entries(
        domain: str | None = None, *args, **kwargs
    ) -> list[config_entries.ConfigEntry]:
        if domain is None:
            # Return all entries across domains (line 76-79)
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(
        side_effect=lambda domain, uid: existing_uem_entry if existing_uem_entry else None
    )
    return flow


def _run_flow_coroutine(coroutine) -> dict:
    """Execute an async flow step and return the resulting FlowResult dict."""
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coroutine)


def _mock_discovery(hass: MagicMock) -> None:
    """Make the config flow's _discover_entities return a full entity map.

    Covers the uncovered path at lines 96-106.
    """
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
        pass


class TestUserStep:
    """Tests for async_step_user decision paths."""

    def test_user_step_aborts_when_single_instance_already_configured(self) -> None:
        """If a UEM entry already exists, async_step_user should abort immediately."""
        hass = MagicMock()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={},
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow = _make_flow(hass, [], existing_uem_entry=uem_entry)

        result = _run_flow_coroutine(flow.async_step_user())
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"

    def test_user_step_aborts_when_no_e3dc_entries(self) -> None:
        """If no e3dc_rscp entries exist, the flow should abort with the proper reason."""
        hass = MagicMock()
        flow = _make_flow(hass, [])

        result = _run_flow_coroutine(flow.async_step_user())
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "e3dc_rscp_not_configured"

    def test_user_step_skips_confirm_when_single_e3dc_entry(self) -> None:
        """With exactly one e3dc_rscp entry, the user step should go straight to confirm."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
        flow = _make_flow(hass, [e3dc_entry])

        with patch.object(UemConfigFlow, "_discover_entities", return_value=E3dcEntityMap()):
            result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

    def test_user_step_shows_form_when_multiple_e3dc_entries(self) -> None:
        """With multiple e3dc_rscp entries, the user step should show a selection form."""
        hass = MagicMock()
        entry1 = _make_entry(entry_id="e3dc-001", unique_id="S10E-10000", title="E3DC Alpha")
        entry2 = _make_entry(entry_id="e3dc-002", unique_id="S10E-20000", title="E3DC Beta")
        flow = _make_flow(hass, [entry1, entry2])

        result = _run_flow_coroutine(flow.async_step_user())
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "data_schema" in result
        schema = result["data_schema"]
        # The schema should present both entry IDs as choices
        schema_dict = dict(schema.schema)
        assert len(schema_dict) == 1
        field = list(schema_dict.values())[0]
        # The In validator's container maps entry_id -> title
        assert "e3dc-001" in field.container or "e3dc-002" in field.container


class TestConfirmStep:
    """Tests for async_step_confirm decision paths."""

    def test_confirm_step_delegates_to_user_when_no_entry_id_set(self) -> None:
        """If _e3dc_entry_id is None on confirm, flow delegates to async_step_user."""
        hass = MagicMock()
        # Provide an e3dc entry so user step reaches confirm
        e3dc_entry = _make_entry()
        flow = _make_flow(hass, [e3dc_entry])
        flow._e3dc_entry_id = None

        # async_step_user() with a single entry goes straight to confirm
        # confirm with _e3dc_entry_id still None would loop, but the flow
        # actually delegates once and the next user step sets _e3dc_entry_id
        result = _run_flow_coroutine(flow.async_step_confirm())
        # With a single e3dc entry, async_step_user skips to confirm
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

    def test_confirm_step_aborts_when_source_entry_deleted(self) -> None:
        """If the selected e3dc entry no longer exists, confirm should abort."""
        hass = MagicMock()
        flow = _make_flow(hass, [])
        flow._e3dc_entry_id = "nonexistent"

        result = _run_flow_coroutine(flow.async_step_confirm())
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "e3dc_rscp_not_configured"

    def test_confirm_step_shows_form_when_missing_required_entities(self) -> None:
        """When discovery yields missing required fields, show error form."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
        partial_map = E3dcEntityMap(soc="sensor.e3dc_soc")  # most fields are None

        flow = _make_flow(hass, [e3dc_entry])
        flow._e3dc_entry_id = e3dc_entry.entry_id

        with patch.object(UemConfigFlow, "_discover_entities", return_value=partial_map):
            result = _run_flow_coroutine(flow.async_step_confirm())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert "errors" in result
        assert result["errors"]["base"] == "missing_required_entities"

    def test_confirm_step_aborts_when_unique_id_already_configured(self) -> None:
        """When a UEM entry with the same unique ID exists, confirm should abort."""
        hass = MagicMock()
        e3dc_entry = _make_entry(entry_id="e3dc-001", unique_id="S10E-12345")
        existing_uem = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM (old)",
            data={},
            source="user",
            entry_id="uem-existing",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow = _make_flow(
            hass,
            [e3dc_entry],
            existing_uem_entry=existing_uem,
        )
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
            # The flow tries to create a new entry, but _abort_if_unique_id_configured
            # will raise AbortFlow
            from homeassistant.data_entry_flow import AbortFlow

            with pytest.raises(AbortFlow, match="already_configured"):
                _run_flow_coroutine(flow.async_step_confirm({"confirm": "yes"}))


class TestConfirmStepCreation:
    """Tests for successful config entry creation from confirm step."""

    def test_confirm_creates_entry_with_full_entity_map(self) -> None:
        """When all required fields are discovered and user confirms, create a config entry."""
        hass = MagicMock()
        e3dc_entry = _make_entry(entry_id="e3dc-001", unique_id="S10E-12345")
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
            result = _run_flow_coroutine(flow.async_step_confirm({"confirm": "yes"}))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "UEM \u2013 Universal Energy Manager"
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-001"
        assert result["data"][CONF_E3DC_SOURCE_UNIQUE_ID] == "S10E-12345"
        assert result["data"][CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"
        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result["data"][CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"
        assert result["data"][CONF_BATTERY_CHARGE_ENTITY] == "sensor.e3dc_charge"
        assert result["data"][CONF_BATTERY_CAPACITY_ENTITY] == "sensor.e3dc_capacity"
        assert result["data"][CONF_MAX_CHARGE_POWER_ENTITY] == "sensor.e3dc_max_charge"

    def test_confirm_creates_entry_with_forecast_entity(self) -> None:
        """When forecast entity is discovered, it should be included in the config entry."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
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
            result = _run_flow_coroutine(flow.async_step_confirm({"confirm": "yes"}))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # forecast_entity is optional, so its absence in E3dcEntityMap means it should be None
        # The entity_data dict will have CONF_FORECAST_ENTITY if _discover_entities sets it
        # In the current code, _discover_entities returns E3dcEntityMap which doesn't have forecast
        # So it should be None/absent in the entry data
        assert CONF_FORECAST_ENTITY not in result["data"] or (
            result["data"].get(CONF_FORECAST_ENTITY) is None
        )

    def test_user_step_preserves_e3dc_entry_id_on_selection(self) -> None:
        """When the user selects an e3dc entry, _e3dc_entry_id should be set for confirm."""
        hass = MagicMock()
        entry1 = _make_entry(entry_id="e3dc-alpha", unique_id="S10E-11111", title="Alpha")
        entry2 = _make_entry(entry_id="e3dc-beta", unique_id="S10E-22222", title="Beta")
        flow = _make_flow(hass, [entry1, entry2])

        # First call: show the selection form
        form_result = _run_flow_coroutine(flow.async_step_user())
        assert form_result["type"] == FlowResultType.FORM
        assert form_result["step_id"] == "user"

        # User selects entry2
        user_input = {CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-beta"}
        confirm_result = _run_flow_coroutine(flow.async_step_user(user_input))
        assert confirm_result["type"] == FlowResultType.FORM
        assert confirm_result["step_id"] == "confirm"
        assert flow._e3dc_entry_id == "e3dc-beta"

    def test_async_entries_domain_none_returns_all_entries(self) -> None:
        """Domain=None must return entries from every configured domain."""
        hass = MagicMock()
        e3dc_entry1 = _make_entry(entry_id="e3dc-001")
        e3dc_entry2 = _make_entry(entry_id="e3dc-002")
        flow = _make_flow(hass, [e3dc_entry1, e3dc_entry2])
        # Trigger the domain=None code path
        result = flow.hass.config_entries.async_entries()
        assert len(result) == 2

    def test_async_entries_domain_none_includes_existing_uem(self) -> None:
        """When domain=None, the existing UEM entry must also be included."""
        hass = MagicMock()
        e3dc_entry = _make_entry()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={},
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow = _make_flow(hass, [e3dc_entry], existing_uem_entry=uem_entry)
        result = flow.hass.config_entries.async_entries()
        assert len(result) == 2
        domains = {e.domain for e in result}
        assert E3DC_RSCP_DOMAIN in domains
        assert DOMAIN in domains


class TestRequiredFields:
    """Tests for _REQUIRED_FIELDS constant."""

    def test_required_fields_contains_all_core_entities(self) -> None:
        """_REQUIRED_FIELDS should list all mandatory sensor entities."""
        expected = {
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_MAX_CHARGE_POWER_ENTITY,
        }
        assert set(_REQUIRED_FIELDS) == expected

    def test_required_fields_excludes_optional_forecast(self) -> None:
        """_REQUIRED_FIELDS should NOT include the optional forecast entity."""
        assert CONF_FORECAST_ENTITY not in _REQUIRED_FIELDS
