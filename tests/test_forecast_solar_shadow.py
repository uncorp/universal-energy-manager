"""Shadow contract: every selected Forecast.Solar source is required.

If any selected Forecast.Solar source is unavailable, malformed, or has no
usable hourly curve, the aggregate must be invalidated and the coordinator
must show an explicit safe forecast diagnostic (\"Shadow – Prognosefehler\").

It must NOT silently skip bad selected sources or combine only the remaining
sources. Legacy UEM entries without selected Forecast.Solar IDs keep their
existing behavior (forecast_connected=False).

This is purely Shadow-only: no HA entity reads, no provider refresh, no API
calls, no credentials.
"""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)


def _setup_entities(hass) -> None:
    """Set up the minimal live-state entities for Shadow coordinator."""
    for entity_id, state, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3.2", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
    ):
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})


def _make_mock_forecast_solar_entry(hass, entry_ids: list[str]) -> MockConfigEntry:
    """Build a UEM config entry with the given Forecast.Solar source IDs."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            CONF_FORECAST_SOLAR_ENTRY_IDS: entry_ids,
        },
    )


def _patch_import_with_fake_fs(
    monkeypatch: pytest.MonkeyPatch,
    fetch_result: dict | None,
) -> None:
    """Replace the forecast_solar.energy module that async_read_forecast_solar
    imports when fetch=None."""

    async def mock_get_solar_forecast(*_args, **_kwargs):
        return fetch_result

    import sys

    fake_mod = type(sys)("homeassistant.components.forecast_solar.energy")
    fake_mod.async_get_solar_forecast = mock_get_solar_forecast
    monkeypatch.setitem(sys.modules, "homeassistant.components.forecast_solar.energy", fake_mod)


# ---------------------------------------------------------------------------
# Test 1: None fetch result → ValueError invalidates aggregate (Shadow contract)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_none_fetch_result_invalidates_aggregate(hass, monkeypatch) -> None:
    """A configured Forecast.Solar source that returns None must invalidate
    the aggregate. The coordinator must show "Shadow – Prognosefehler" rather
    than silently degrading to forecast_connected=False."""
    _setup_entities(hass)
    _patch_import_with_fake_fs(monkeypatch, None)

    coordinator = UemShadowCoordinator(hass, _make_mock_forecast_solar_entry(hass, ["roof"]))
    await coordinator.async_refresh()

    assert coordinator.data.commands_sent is False
    assert coordinator.data.forecast_connected is False
    assert coordinator.data.status == "Shadow – Prognosefehler"
    assert coordinator.data.error is not None


# ---------------------------------------------------------------------------
# Test 2: missing wh_hours key → ValueError invalidates aggregate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_wh_hours_key_invalidates_aggregate(hass, monkeypatch) -> None:
    """A configured source that returns a dict without wh_hours must
    invalidate the aggregate with a clear diagnostic."""
    _setup_entities(hass)
    _patch_import_with_fake_fs(monkeypatch, {"version": "2.0", "lat": 48.0})

    coordinator = UemShadowCoordinator(hass, _make_mock_forecast_solar_entry(hass, ["roof"]))
    await coordinator.async_refresh()

    assert coordinator.data.commands_sent is False
    assert coordinator.data.forecast_connected is False
    assert coordinator.data.status == "Shadow – Prognosefehler"
    assert coordinator.data.error is not None


# ---------------------------------------------------------------------------
# Test 3: empty wh_hours → ValueError invalidates aggregate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_wh_hours_invalidates_aggregate(hass, monkeypatch) -> None:
    """A configured source that returns an empty wh_hours curve must
    invalidate the aggregate with a clear diagnostic."""
    _setup_entities(hass)
    _patch_import_with_fake_fs(monkeypatch, {"wh_hours": {}})

    coordinator = UemShadowCoordinator(hass, _make_mock_forecast_solar_entry(hass, ["roof"]))
    await coordinator.async_refresh()

    assert coordinator.data.commands_sent is False
    assert coordinator.data.forecast_connected is False
    assert coordinator.data.status == "Shadow – Prognosefehler"
    assert coordinator.data.error is not None


# ---------------------------------------------------------------------------
# Test 4: legacy entry without CONF_FORECAST_SOLAR_ENTRY_IDS → unchanged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_legacy_no_forecast_config_still_works(hass) -> None:
    """A config entry without CONF_FORECAST_SOLAR_ENTRY_IDS should behave
    exactly as before: forecast_connected=False, no error."""
    _setup_entities(hass)

    coordinator = UemShadowCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            },
        ),
    )
    await coordinator.async_refresh()

    assert coordinator.data.commands_sent is False
    assert coordinator.data.error is None
    assert coordinator.data.forecast_connected is False
    assert coordinator.data.status == "Shadow – keine aktive Steuerung"
