"""Tests for UemActiveSwitch and UemStrategySelect sensors.

Verifies the shadow-only switch stays off and the strategy select
persists changes to the config entry.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    STRATEGY_OPTIONS,
)
from custom_components.universal_energy_manager.coordinator import (
    ShadowData,
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.sensor import (
    UemActiveSwitch,
    UemStrategySelect,
)


def _make_entry(
    entry_id: str = "uem-entry",
    strategy: str = "pv_first",
    unique_id: str = "test-identity",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM – Universal Energy Manager",
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
            "strategy": strategy,
        },
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.NOT_LOADED,
    )


def _make_coordinator(hass, strategy: str = "pv_first") -> UemShadowCoordinator:
    entry = _make_entry(strategy=strategy)
    coordinator = UemShadowCoordinator(hass, entry)
    coordinator.data = ShadowData(
        status="Shadow – keine aktive Steuerung",
        decision="Livewerte gültig; Soll-Ladelimit: 3000 W.",
        planned_charge_limit_w=3000.0,
        error=None,
        forecast_connected=True,
        pv_power_w=2500.0,
        house_power_w=600.0,
        strategy=strategy,
    )
    return coordinator


class TestUemActiveSwitch:
    """Tests for the master active-control switch (always off in Shadow mode)."""

    def test_is_on_is_always_false(self, hass) -> None:
        """The switch must always report off in Shadow mode."""
        entry = _make_entry()
        coordinator = UemShadowCoordinator(hass, entry)
        coordinator.data = ShadowData(
            status="Shadow – keine aktive Steuerung",
            decision="Livewerte gültig; Soll-Ladelimit: 0 W.",
            planned_charge_limit_w=0.0,
            error=None,
            forecast_connected=False,
            pv_power_w=0.0,
            house_power_w=0.0,
            strategy="pv_first",
        )
        switch = UemActiveSwitch(coordinator, entry)
        assert switch.is_on is False

    def test_attributes_show_shadow_only(self, hass) -> None:
        """Extra state attributes must confirm shadow-only and opt-in."""
        coordinator = _make_coordinator(hass)
        entry = _make_entry()
        switch = UemActiveSwitch(coordinator, entry)
        attrs = switch.extra_state_attributes
        assert attrs["shadow_only"] is True
        assert attrs["requires_opt_in"] is True

    def test_inherits_switch_entity_base(self, hass) -> None:
        """The sensor class must be a proper SwitchEntity."""
        coordinator = _make_coordinator(hass)
        entry = _make_entry()
        switch = UemActiveSwitch(coordinator, entry)
        assert isinstance(switch, SwitchEntity)

    @pytest.mark.asyncio
    async def test_turn_on_is_blocked(self, hass) -> None:
        """Calling async_turn_on must not enable active control."""
        entry = _make_entry()
        coordinator = _make_coordinator(hass)
        switch = UemActiveSwitch(coordinator, entry)
        switch.hass = hass
        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_on()
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_off_is_noop(self, hass) -> None:
        """Calling async_turn_off must keep the switch off."""
        entry = _make_entry()
        coordinator = _make_coordinator(hass)
        switch = UemActiveSwitch(coordinator, entry)
        switch.hass = hass
        with patch.object(switch, "async_write_ha_state"):
            await switch.async_turn_off()
        assert switch.is_on is False


class TestUemStrategySelect:
    """Tests for the strategy selection sensor."""

    def test_current_option_matches_coordinator_data(self, hass) -> None:
        """When coordinator has data, the strategy must come from it."""
        entry = _make_entry(strategy="battery_first")
        coordinator = _make_coordinator(hass, strategy="battery_first")
        select = UemStrategySelect(coordinator, entry)
        assert select.current_option == "battery_first"

    def test_current_option_falls_back_to_entry_data(self, hass) -> None:
        """When coordinator has no data, fall back to entry data."""
        entry = _make_entry(strategy="balanced")
        coordinator = UemShadowCoordinator(hass, entry)
        coordinator.data = None
        select = UemStrategySelect(coordinator, entry)
        assert select.current_option == "balanced"

    def test_current_option_falls_back_to_default(self, hass) -> None:
        """When entry has no strategy, fall back to pv_first."""
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM – Universal Energy Manager",
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
            },
            source="user",
            entry_id="uem-def",
            unique_id="test-identity",
            state=config_entries.ConfigEntryState.NOT_LOADED,
        )
        coordinator = UemShadowCoordinator(hass, entry)
        coordinator.data = None
        select = UemStrategySelect(coordinator, entry)
        assert select.current_option == "pv_first"

    def test_options_contains_all_strategies(self, hass) -> None:
        """Available options must match STRATEGY_OPTIONS."""
        coordinator = _make_coordinator(hass)
        entry = _make_entry()
        select = UemStrategySelect(coordinator, entry)
        assert select.options == STRATEGY_OPTIONS

    def test_options_contains_pv_first(self, hass) -> None:
        """pv_first must be in available options."""
        coordinator = _make_coordinator(hass)
        entry = _make_entry()
        select = UemStrategySelect(coordinator, entry)
        assert "pv_first" in select.options

    @pytest.mark.asyncio
    async def test_select_option_persists_to_entry(self, hass) -> None:
        """Changing the strategy must update the config entry data."""
        entry = _make_entry(strategy="pv_first")
        hass.config_entries._entries[entry.entry_id] = entry  # type: ignore[attr-defined]
        coordinator = _make_coordinator(hass, strategy="pv_first")
        select = UemStrategySelect(coordinator, entry)
        select.hass = hass
        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("battery_first")
        assert entry.data.get("strategy") == "battery_first"

    def test_inherits_select_entity_base(self, hass) -> None:
        """The sensor class must be a proper SelectEntity."""
        coordinator = _make_coordinator(hass)
        entry = _make_entry()
        select = UemStrategySelect(coordinator, entry)
        assert isinstance(select, SelectEntity)

    @pytest.mark.asyncio
    async def test_select_strategy_invalid_option(self, hass) -> None:
        """Selecting a non-existent option still persists (HA validates at UI level)."""
        entry = _make_entry(strategy="pv_first")
        hass.config_entries._entries[entry.entry_id] = entry  # type: ignore[attr-defined]
        coordinator = _make_coordinator(hass, strategy="pv_first")
        select = UemStrategySelect(coordinator, entry)
        select.hass = hass
        with patch.object(select, "async_write_ha_state"):
            await select.async_select_option("unknown_strategy")
        assert entry.data.get("strategy") == "unknown_strategy"
