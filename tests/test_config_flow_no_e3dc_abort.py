"""TDD test for the v0.1.1 bug: confirm step with missing e3dc_rscp must NOT abort.

Bug: In a fresh HAOS instance, adding UEM without e3dc_rscp configured caused
`e3dc_rscp_not_configured` abort in the confirm step instead of showing the
choice to proceed with manual mapping.

Fix: Confirm step delegates to no_e3dc_choice when the e3dc entry is not found,
allowing the user to cancel (set up adapter first) or continue (manual mapping).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
)


def _make_entry(
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


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all_entries_by_domain: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
        FORECAST_SOLAR_DOMAIN: [],
    }

    def _async_entries(domain: str | None = None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


def _run(coroutine) -> dict:
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coroutine
    )


def _make_manual_data():
    return {
        CONF_SOC_ENTITY: "sensor.manual_soc",
        CONF_PV_POWER_ENTITY: "sensor.manual_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
    }


def _mock_location(hass: MagicMock) -> None:
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TDD TEST 1: confirm with deleted/missing e3dc entry → NO abort, show choice #
# =========================================================================== #

class TestConfirmNoAbortOnMissingE3dc:
    """Bug fix: confirm step must NOT abort when e3dc entry is missing."""

    def test_confirm_missing_e3dc_shows_choice_not_abort(self) -> None:
        """When e3dc entry was deleted or never existed, confirm shows the
        choice form (cancel or continue with manual) instead of aborting."""
        hass = MagicMock()
        flow = _make_flow(hass, [])  # No e3dc entries at all
        flow._e3dc_entry_id = "nonexistent"  # Pretend we had one

        result = _run(flow.async_step_confirm())

        # BUG: v0.1.1 returns ABORT with reason "e3dc_rscp_not_configured" here.
        # FIX: must show the choice form.
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "no_e3dc_choice"


# =========================================================================== #
# TDD TEST 2: full happy path without e3dc_rscp in fresh HAOS                #
# =========================================================================== #

class TestFreshHaosNoE3dcFullPath:
    """Simulates adding UEM in a fresh HAOS without e3dc_rscp installed."""

    def test_user_flow_no_e3dc_then_manual_creates_entry(self) -> None:
        """User adds UEM → no e3dc found → continues → manual mapping → entry."""
        hass = MagicMock()
        _mock_location(hass)
        flow = _make_flow(hass, [])

        # Step 1: user adds integration — should show choice, not abort
        result = _run(flow.async_step_user())
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "no_e3dc_choice"

        # Step 2: user chooses to continue with manual mapping
        result = _run(
            flow.async_step_no_e3dc_choice({"confirm": "continue"})
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_mapping"

        # Step 3: submit all required entities
        result = _run(flow.async_step_manual_mapping(_make_manual_data()))
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] is None
        assert result["data"][CONF_E3DC_SOURCE_UNIQUE_ID] is None
        assert result["data"].get(CONF_MANUAL_ENTITIES) is True
        assert result["data"][CONF_SOC_ENTITY] == "sensor.manual_soc"


# =========================================================================== #
# TDD TEST 3: confirm with _e3dc_entry_id=None (no_e3dc_choice path)        #
# =========================================================================== #

class TestConfirmDelegatedNoE3dcChoice:
    """When _e3dc_entry_id is None on confirm, delegate to no_e3dc_choice."""

    def test_confirm_none_entry_id_goes_to_choice(self) -> None:
        """_e3dc_entry_id=None → no_e3dc_choice form."""
        hass = MagicMock()
        flow = _make_flow(hass, [])
        flow._e3dc_entry_id = None

        result = _run(flow.async_step_confirm())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "no_e3dc_choice"


# =========================================================================== #
# TDD TEST 4: reconfigure with deleted e3dc → must NOT silently abort       #
# =========================================================================== #

class TestReconfigureDeletedE3dc:
    """Reconfigure must handle deleted e3dc_rscp gracefully."""

    def test_reconfigure_rescan_deleted_e3dc_no_silent_overwrite(self) -> None:
        """When e3dc_rscp entry was deleted, rescan must abort (not silently
        overwrite manual values). The reason should indicate the adapter is gone."""
        hass = MagicMock()
        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-deleted",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                CONF_MANUAL_ENTITIES: False,
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

        # Mock async_entries to return the UEM entry for DOMAIN lookups
        ce = hass.config_entries
        _all_entries = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain: str | None = None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in _all_entries.values():
                    result.extend(entries)
                return result
            return _all_entries.get(domain, [])

        ce.async_entries = MagicMock(side_effect=_async_entries)
        ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)

        # Rescan when e3dc is gone → should abort with e3dc_rscp_not_configured
        result = _run(flow.async_step_reconfigure({"rescan_e3dc": True, "edit_manual": False}))

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "e3dc_rscp_not_configured"
