"""Tests for UemCurrentGenerationSensor and UemTotalLoadSensor.

Shadow-only: no entity writes, no service calls, no credentials.
"""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import ShadowData
from custom_components.universal_energy_manager.sensor import (
    UemCurrentGenerationSensor,
    UemTotalLoadSensor,
)


def _make_mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
        },
        unique_id="test-identity",
        entry_id="uem-entry",
    )


def _make_mock_coordinator_data(
    pv_power_w: float = 3200.0,
    house_power_w: float = 800.0,
) -> ShadowData:
    return ShadowData(
        status="Shadow – keine aktive Steuerung",
        decision="Livewerte gültig; PV-Prognose verbunden.",
        planned_charge_limit_w=4500.0,
        error=None,
        forecast_connected=True,
        pv_power_w=pv_power_w,
        house_power_w=house_power_w,
        strategy="pv_first",
    )


def _make_mock_coordinator(hass, pv_power_w: float = 3200.0, house_power_w: float = 800.0):
    """Create a coordinator with valid data."""
    entry = _make_mock_entry()
    coordinator = __import__(
        "custom_components.universal_energy_manager.coordinator",
        fromlist=["UemShadowCoordinator"],
    ).UemShadowCoordinator(hass, entry)
    coordinator.data = _make_mock_coordinator_data(pv_power_w, house_power_w)
    return coordinator, entry


class TestUemCurrentGenerationSensor:
    """Tests for the PV generation current-power sensor."""

    def test_exposes_pv_power_value(self, hass) -> None:
        """The generation sensor must expose the coordinator's PV power."""
        coordinator, entry = _make_mock_coordinator(hass, pv_power_w=2500.0, house_power_w=600.0)
        sensor = UemCurrentGenerationSensor(coordinator, entry)
        assert sensor.native_value == 2500.0

    def test_defaults_to_zero_when_no_data(self, hass) -> None:
        """When coordinator has no data, generation must default to 0."""
        entry = _make_mock_entry()
        coordinator = __import__(
            "custom_components.universal_energy_manager.coordinator",
            fromlist=["UemShadowCoordinator"],
        ).UemShadowCoordinator(hass, entry)
        coordinator.data = None
        sensor = UemCurrentGenerationSensor(coordinator, entry)
        assert sensor.native_value == 0.0

    def test_zero_pv_power(self, hass) -> None:
        """Zero PV power is a valid reading (e.g. night time)."""
        coordinator, entry = _make_mock_coordinator(hass, pv_power_w=0.0, house_power_w=500.0)
        sensor = UemCurrentGenerationSensor(coordinator, entry)
        assert sensor.native_value == 0.0


class TestUemTotalLoadSensor:
    """Tests for the total house load sensor."""

    def test_exposes_house_power_value(self, hass) -> None:
        """The total load sensor must expose the coordinator's house power."""
        coordinator, entry = _make_mock_coordinator(hass, pv_power_w=3000.0, house_power_w=1200.0)
        sensor = UemTotalLoadSensor(coordinator, entry)
        assert sensor.native_value == 1200.0

    def test_defaults_to_zero_when_no_data(self, hass) -> None:
        """When coordinator has no data, total load must default to 0."""
        entry = _make_mock_entry()
        coordinator = __import__(
            "custom_components.universal_energy_manager.coordinator",
            fromlist=["UemShadowCoordinator"],
        ).UemShadowCoordinator(hass, entry)
        coordinator.data = None
        sensor = UemTotalLoadSensor(coordinator, entry)
        assert sensor.native_value == 0.0

    def test_high_house_load(self, hass) -> None:
        """High house load is correctly reported."""
        coordinator, entry = _make_mock_coordinator(hass, pv_power_w=1000.0, house_power_w=5000.0)
        sensor = UemTotalLoadSensor(coordinator, entry)
        assert sensor.native_value == 5000.0
