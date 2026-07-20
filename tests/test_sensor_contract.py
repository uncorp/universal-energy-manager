"""Contract tests for UEM shadow sensors.

Verifies that the three Shadow-mode sensors expose correct attributes
and values when the coordinator has data, and safe defaults when it
doesn't yet.

Shadow-only: no entity writes, no service calls, no credentials.
"""

import pytest
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
from custom_components.universal_energy_manager.coordinator import (
    ShadowData,
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.sensor import (
    UemDecisionSensor,
    UemPlannedChargeLimitSensor,
    UemStatusSensor,
)


def _make_mock_coordinator_data(
    status: str = "Shadow – keine aktive Steuerung",
    decision: str = (
        "Livewerte gültig; PV-Prognose verbunden. Berechne Ladevorgabe. "
        "Soll-Ladelimit: 4500 W."
    ),
    planned_charge_limit_w: float = 4500.0,
    error: str | None = None,
    forecast_connected: bool = True,
    pv_power_w: float = 3200.0,
    house_power_w: float = 800.0,
    strategy: str = "pv_first",
) -> ShadowData:
    return ShadowData(
        status=status,
        decision=decision,
        planned_charge_limit_w=planned_charge_limit_w,
        error=error,
        forecast_connected=forecast_connected,
        pv_power_w=pv_power_w,
        house_power_w=house_power_w,
        strategy=strategy,
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


@pytest.fixture()
def mock_coordinator_with_data(hass) -> UemShadowCoordinator:
    """Coordinator with valid ShadowData."""
    entry = _make_mock_entry()
    coordinator = UemShadowCoordinator(hass, entry)
    coordinator.data = _make_mock_coordinator_data()
    return coordinator


@pytest.fixture()
def mock_coordinator_no_data(hass) -> UemShadowCoordinator:
    """Coordinator with no data yet (initial state)."""
    entry = _make_mock_entry()
    coordinator = UemShadowCoordinator(hass, entry)
    coordinator.data = None
    return coordinator


class TestUemStatusSensor:
    """Tests for UemStatusSensor."""

    def test_status_sensor_exposes_shadow_status(self, mock_coordinator_with_data) -> None:
        """The status sensor must always show the coordinator's status string."""
        sensor = UemStatusSensor(mock_coordinator_with_data, _make_mock_entry())
        assert sensor.native_value == "Shadow – keine aktive Steuerung"

    def test_status_sensor_exposes_error_status(self, hass) -> None:
        """When coordinator has an error, the status must reflect it."""
        entry = _make_mock_entry()
        coordinator = UemShadowCoordinator(hass, entry)
        coordinator.data = _make_mock_coordinator_data(
            status="Shadow – Messdatenfehler",
            decision="E3DC-Messwerte sind unvollständig oder ungültig; keine Steuerung aktiv.",
            error="test error",
            forecast_connected=False,
        )
        sensor = UemStatusSensor(coordinator, entry)
        assert sensor.native_value == "Shadow – Messdatenfehler"

    def test_status_sensor_attributes_show_no_active_control(
        self, mock_coordinator_with_data,
    ) -> None:
        """Extra state attributes must confirm no active control."""
        sensor = UemStatusSensor(mock_coordinator_with_data, _make_mock_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["active_control"] is False
        assert attrs["commands_sent"] is False
        assert attrs["forecast_connected"] is True
        assert attrs["last_error"] is None

    def test_status_sensor_defaults_when_no_coordinator_data(
        self, mock_coordinator_no_data,
    ) -> None:
        """When coordinator has no data, the sensor must show the default status."""
        from custom_components.universal_energy_manager.sensor import SHADOW_STATUS

        sensor = UemStatusSensor(mock_coordinator_no_data, _make_mock_entry())
        assert sensor.native_value == SHADOW_STATUS


class TestUemDecisionSensor:
    """Tests for UemDecisionSensor."""

    def test_decision_sensor_exposes_coordinator_decision(self, mock_coordinator_with_data) -> None:
        """The decision sensor must surface the coordinator's decision string."""
        sensor = UemDecisionSensor(mock_coordinator_with_data, _make_mock_entry())
        assert "Livewerte gültig" in sensor.native_value
        assert "4500 W" in sensor.native_value

    def test_decision_sensor_defaults_when_no_data(self, mock_coordinator_no_data) -> None:
        """When coordinator has no data, show a waiting message."""
        sensor = UemDecisionSensor(mock_coordinator_no_data, _make_mock_entry())
        assert sensor.native_value == "Warte auf erste Planungsdaten"


class TestUemPlannedChargeLimitSensor:
    """Tests for UemPlannedChargeLimitSensor."""

    def test_planned_charge_limit_sensor_exposes_value(self, mock_coordinator_with_data) -> None:
        """The charge limit sensor must expose the coordinator's planned limit."""
        sensor = UemPlannedChargeLimitSensor(mock_coordinator_with_data, _make_mock_entry())
        assert sensor.native_value == 4500.0

    def test_planned_charge_limit_sensor_defaults_to_zero(self, mock_coordinator_no_data) -> None:
        """When coordinator has no data, the charge limit must default to 0."""
        sensor = UemPlannedChargeLimitSensor(mock_coordinator_no_data, _make_mock_entry())
        assert sensor.native_value == 0.0

    def test_planned_charge_limit_sensor_attributes(self, mock_coordinator_with_data) -> None:
        """Extra state attributes must confirm shadow-only operation."""
        sensor = UemPlannedChargeLimitSensor(mock_coordinator_with_data, _make_mock_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["shadow_only"] is True
        assert attrs["command_sent"] is False

    def test_planned_charge_limit_sensor_has_watt_unit(self, mock_coordinator_with_data) -> None:
        """The sensor must declare watts as its unit of measurement."""
        from homeassistant.const import UnitOfPower

        sensor = UemPlannedChargeLimitSensor(mock_coordinator_with_data, _make_mock_entry())
        assert sensor.unit_of_measurement == UnitOfPower.WATT
