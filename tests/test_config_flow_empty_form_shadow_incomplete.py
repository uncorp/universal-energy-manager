"""Regression test: empty form → CREATE_ENTRY → Shadow incomplete (Req 4).

Requirement 4 states:
- No entity or fixed capacity/power is mandatory
- OK/Speichern must work even with a completely empty form
- Entry stays in "Shadow – Einrichtung unvollständig" status and does not
  plan or control

This test exercises the full config-flow path (no_e3dc_choice →
manual_mapping → CREATE_ENTRY) with an empty submission and then verifies
that the resulting entry data triggers the Shadow incomplete path in the
coordinator.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_MANUAL_ENTITIES,
    SHADOW_STATUS_UNVOLLSTANDIG,
)
from custom_components.universal_energy_manager.coordinator import (
    ShadowData,
    UemShadowCoordinator,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _run(coro):
    """Run a coroutine on a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list | None = None,
) -> UemConfigFlow:
    """Create a UemConfigFlow with the given hass and pre-populated entries."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    if e3dc_entries is None:
        e3dc_entries = []

    _all: dict[str, list] = {E3DC_RSCP_DOMAIN: e3dc_entries, DOMAIN: []}

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all.values():
                result.extend(entries)
            return result
        return _all.get(domain, [])

    flow.hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
    flow.hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
        return_value=None
    )
    return flow


def _mock_location(hass: MagicMock, lat=52.5200, lon=13.4050):
    loc = MagicMock()
    loc.latitude = lat
    loc.longitude = lon
    hass.config.location = loc


# =========================================================================== #
# TEST 1: Empty form through manual_mapping creates a valid entry             #
# =========================================================================== #


class TestEmptyFormCreatesEntry:
    """Submitting an empty form via manual_mapping must create an entry."""

    def test_empty_dict_creates_entry(self) -> None:
        """An empty dict {} submitted to manual_mapping must succeed."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        # Step 1: no_e3dc_choice
        result = _run(
            flow.async_step_no_e3dc_choice({"confirm": "continue"})
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"

        # Step 2: submit empty dict
        result = _run(flow.async_step_manual_mapping({}))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "UEM – Universal Energy Manager (Manual)"
        # Manual entry flags
        assert result["data"][CONF_MANUAL_ENTITIES] is True
        assert result["data"]["e3dc_config_entry_id"] is None
        assert result["data"]["e3dc_source_unique_id"] is None

    def test_whitespace_only_strings_create_entry(self) -> None:
        """Whitespace-only values submitted to manual_mapping must succeed."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        result = _run(
            flow.async_step_manual_mapping(
                {
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
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY


# =========================================================================== #
# TEST 2: "Later" path also creates empty entry                               #
# =========================================================================== #


class TestLaterPathCreatesEntry:
    """Selecting 'later' on no_e3dc_choice also goes through manual_mapping."""

    def test_later_creates_empty_entry(self) -> None:
        """'later' choice → manual_mapping with empty → CREATE_ENTRY."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        result = _run(
            flow.async_step_no_e3dc_choice({"confirm": "later"})
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "UEM – Universal Energy Manager (Manual)"
        assert result["data"][CONF_MANUAL_ENTITIES] is True


# =========================================================================== #
# TEST 3: Empty entry → coordinator → Shadow incomplete                       #
# =========================================================================== #


class TestEmptyEntryShadowIncomplete:
    """An entry created with empty fields must result in Shadow incomplete."""

    def _make_entry(self, data: dict) -> config_entries.ConfigEntry:
        return config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM – Universal Energy Manager (Manual)",
            data=data,
            source="user",
            entry_id="uem-empty-test",
            unique_id="uem:manual:52.5200,13.4050",
            state=config_entries.ConfigEntryState.LOADED,
        )

    def test_empty_entry_triggers_shadow_incomplete(self) -> None:
        """Entry with all entity fields empty → Shadow incomplete."""
        hass = MagicMock()
        entry = self._make_entry(
            {
                "e3dc_config_entry_id": None,
                "e3dc_source_unique_id": None,
                CONF_MANUAL_ENTITIES: True,
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
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = _run(coord._async_update_data())

        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert result.commands_sent is False
        assert result.planned_charge_limit_w == 0.0
        assert result.error is not None

    def test_all_whitespace_entry_triggers_shadow_incomplete(self) -> None:
        """Entry with all whitespace values → Shadow incomplete."""
        hass = MagicMock()
        entry = self._make_entry(
            {
                "e3dc_config_entry_id": None,
                "e3dc_source_unique_id": None,
                CONF_MANUAL_ENTITIES: True,
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
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = _run(coord._async_update_data())

        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert result.commands_sent is False

    def test_partial_entry_still_shadow_incomplete(self) -> None:
        """Entry with only some core entities set → Shadow incomplete."""
        hass = MagicMock()
        entry = self._make_entry(
            {
                "e3dc_config_entry_id": None,
                "e3dc_source_unique_id": None,
                CONF_MANUAL_ENTITIES: True,
                "soc_entity": "sensor.soc_only",
                "pv_power_entity": "sensor.pv_only",
                "house_power_entity": "",
                "battery_charge_entity": "",
                "battery_capacity_entity": "",
                "battery_manual_capacity_kwh": "",
                "max_charge_power_entity": "",
                "max_charge_manual_power_w": "",
                "grid_export_entity": "",
            }
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = _run(coord._async_update_data())

        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert result.commands_sent is False


# =========================================================================== #
# TEST 4: Flow + coordinator consistency                                      #
# =========================================================================== #


class TestFlowCoordinatorConsistency:
    """The data created by the flow must be consistent with the coordinator's
    incomplete check. This is the end-to-end regression for Req 4."""

    def test_flow_empty_then_coordinator_incomplete(self) -> None:
        """Full path: user → no_e3dc → manual_mapping(empty) → CREATE_ENTRY →
        coordinator reports Shadow incomplete."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, e3dc_entries=[])

        # Flow path
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))
        flow_result = _run(flow.async_step_manual_mapping({}))

        assert flow_result["type"] == FlowResultType.CREATE_ENTRY
        entry_data = flow_result["data"]

        # Now create a ConfigEntry from the flow result data
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title=flow_result["title"],
            data=entry_data,
            source="user",
            entry_id="uem-empty-test",
            unique_id=entry_data.get(
                "unique_id", "uem:manual:52.5200,13.4050"
            ),
            state=config_entries.ConfigEntryState.LOADED,
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        # Coordinator check
        coord = UemShadowCoordinator(hass, entry)
        coord_result = _run(coord._async_update_data())

        # Assert: flow created an entry AND coordinator flags it incomplete
        assert isinstance(coord_result, ShadowData)
        assert coord_result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert coord_result.commands_sent is False
