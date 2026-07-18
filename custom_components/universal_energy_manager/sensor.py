"""Deliberately read-only UEM Shadow sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SHADOW_STATUS, UemShadowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the small read-only status and planner-output sensor set."""
    coordinator: UemShadowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UemStatusSensor(coordinator, entry),
            UemDecisionSensor(coordinator, entry),
            UemPlannedChargeLimitSensor(coordinator, entry),
        ]
    )


class _UemSensor(CoordinatorEntity[UemShadowCoordinator], SensorEntity):
    """Shared identity details for UEM's Shadow-mode sensor set."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UemShadowCoordinator, entry: ConfigEntry, suffix: str) -> None:
        """Initialize a stable entity identity without storing source credentials."""
        super().__init__(coordinator)
        stable_entry_identity = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{stable_entry_identity}_{suffix}"


class UemStatusSensor(_UemSensor):
    """State the safety mode unambiguously."""

    _attr_name = "Status"
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, coordinator: UemShadowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "status")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status if self.coordinator.data else SHADOW_STATUS

    @property
    def extra_state_attributes(self) -> dict[str, bool | str | None]:
        data = self.coordinator.data
        return {
            "active_control": False,
            "commands_sent": False,
            "last_error": data.error if data else "no coordinator data",
        }


class UemDecisionSensor(_UemSensor):
    """Explain what UEM currently knows, without pretending to control anything."""

    _attr_name = "Entscheidung"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: UemShadowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "decision")

    @property
    def native_value(self) -> str:
        if self.coordinator.data is None:
            return "Warte auf erste Planungsdaten"
        return self.coordinator.data.decision


class UemPlannedChargeLimitSensor(_UemSensor):
    """Expose the calculated limit; the Shadow implementation never applies it."""

    _attr_name = "Soll-Akku-Ladelimit"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:battery-charging-outline"

    def __init__(self, coordinator: UemShadowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "planned_charge_limit")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.planned_charge_limit_w if self.coordinator.data else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        return {"shadow_only": True, "command_sent": False}
