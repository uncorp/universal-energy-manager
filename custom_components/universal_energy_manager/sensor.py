"""Initial, deliberately read-only UEM Shadow sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

SHADOW_STATUS = "Shadow – keine aktive Steuerung"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the initial read-only status and planner-output sensors."""
    async_add_entities(
        [
            UemStatusSensor(entry),
            UemDecisionSensor(entry),
            UemPlannedChargeLimitSensor(entry),
        ]
    )


class _UemSensor(SensorEntity):
    """Shared identity details for UEM's small Shadow-mode sensor set."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, suffix: str) -> None:
        """Initialize a stable entity identity without keeping secrets in state."""
        stable_entry_identity = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{stable_entry_identity}_{suffix}"


class UemStatusSensor(_UemSensor):
    """State the safety mode unambiguously."""

    _attr_name = "Status"
    _attr_icon = "mdi:shield-check-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "status")

    @property
    def native_value(self) -> str:
        return SHADOW_STATUS

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        return {"active_control": False, "commands_sent": False}


class UemDecisionSensor(_UemSensor):
    """Explain what UEM currently knows, without pretending to control anything."""

    _attr_name = "Entscheidung"
    _attr_icon = "mdi:brain"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "decision")

    @property
    def native_value(self) -> str:
        return "Warte auf erste Planungsdaten"


class UemPlannedChargeLimitSensor(_UemSensor):
    """Expose the calculated limit; the Shadow implementation never applies it."""

    _attr_name = "Soll-Akku-Ladelimit"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:battery-charging-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "planned_charge_limit")

    @property
    def native_value(self) -> float:
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        return {"shadow_only": True, "command_sent": False}
