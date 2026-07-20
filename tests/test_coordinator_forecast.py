"""Tests for optional forecast entity support in the Shadow coordinator."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.universal_energy_manager.coordinator import ShadowData, UemShadowCoordinator


@dataclass(frozen=True)
class MockState:
    """Minimal frozen state mock to avoid MagicMock recursion."""
    state: str
    attributes: dict = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime(2026, 7, 18, 10, 0, tzinfo=UTC))


def _make_state(
    state_value: str = "55",
    unit: str = "%",
    updated: datetime | None = None,
) -> MockState:
    return MockState(
        state=state_value,
        attributes={"unit_of_measurement": unit},
        last_updated=updated or datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )


@pytest.fixture()
def entry_with_forecast():
    """Config entry that includes an optional forecast entity."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain="universal_energy_manager",
        title="UEM",
        data={
            "soc_entity": "sensor.e3dc_soc",
            "pv_power_entity": "sensor.e3dc_pv",
            "house_power_entity": "sensor.e3dc_house",
            "grid_export_entity": "sensor.e3dc_grid",
            "battery_charge_entity": "sensor.e3dc_charge",
            "battery_capacity_entity": "sensor.e3dc_capacity",
            "max_charge_power_entity": "sensor.e3dc_max_charge",
            "forecast_entity": "sensor.e3dc_forecast",
        },
        source="user",
        entry_id="uem-entry",
    )


@pytest.fixture()
def entry_without_forecast():
    """Config entry without an optional forecast entity."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain="universal_energy_manager",
        title="UEM",
        data={
            "soc_entity": "sensor.e3dc_soc",
            "pv_power_entity": "sensor.e3dc_pv",
            "house_power_entity": "sensor.e3dc_house",
            "grid_export_entity": "sensor.e3dc_grid",
            "battery_charge_entity": "sensor.e3dc_charge",
            "battery_capacity_entity": "sensor.e3dc_capacity",
            "max_charge_power_entity": "sensor.e3dc_max_charge",
        },
        source="user",
        entry_id="uem-entry-no-fc",
    )


def test_shadow_data_exposes_forecast_connected_when_false() -> None:
    data = ShadowData(
        status="Shadow – Messdatenfehler",
        decision="Keine Vorhersage",
        planned_charge_limit_w=0.0,
        error="test error",
        forecast_connected=False,
        pv_power_w=0.0,
        house_power_w=0.0,
        strategy="pv_first",
    )
    assert data.forecast_connected is False


def test_shadow_data_exposes_forecast_connected_when_true() -> None:
    data = ShadowData(
        status="Shadow – keine aktive Steuerung",
        decision="PV-Prognose verbunden",
        planned_charge_limit_w=2000.0,
        error=None,
        forecast_connected=True,
        pv_power_w=3200.0,
        house_power_w=800.0,
        strategy="battery_first",
    )
    assert data.forecast_connected is True


def test_coordinator_sets_forecast_connected_false_when_entity_missing(
    entry_without_forecast: ConfigEntry,
) -> None:
    """When no forecast entity is configured, _forecast_connected() must return False."""
    hass = MagicMock()
    coordinator = UemShadowCoordinator(hass, entry_without_forecast)
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    def _get_state(entity_id: str) -> MockState:
        return _make_state(updated=now)

    hass.states.get.side_effect = _get_state

    import asyncio

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coordinator._async_update_data()
    )
    assert hasattr(result, "forecast_connected")
    assert result.forecast_connected is False


def test_coordinator_sets_forecast_connected_true_when_entity_present_and_valid(
    entry_with_forecast: ConfigEntry,
) -> None:
    """When a forecast entity is configured and provides valid state,
    forecast_connected should be True."""
    hass = MagicMock()
    coordinator = UemShadowCoordinator(hass, entry_with_forecast)
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    def _get_state(entity_id: str) -> MockState:
        if entity_id == "sensor.e3dc_forecast":
            return MockState(
                state="10:00",
                attributes={"forecast": [{"power_w": 3000.0}]},
                last_updated=now,
            )
        return _make_state(updated=now)

    hass.states.get.side_effect = _get_state

    import asyncio

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coordinator._async_update_data()
    )
    assert result.forecast_connected is True


def test_coordinator_forecast_entity_unavailable_sets_connected_false(
    entry_with_forecast: ConfigEntry,
) -> None:
    """If the forecast entity state is unavailable, forecast_connected must be False."""
    hass = MagicMock()
    coordinator = UemShadowCoordinator(hass, entry_with_forecast)
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    def _get_state(entity_id: str) -> MockState:
        return MockState(
            state="unavailable",
            last_updated=now,
        )

    hass.states.get.side_effect = _get_state

    import asyncio

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coordinator._async_update_data()
    )
    assert result.forecast_connected is False
