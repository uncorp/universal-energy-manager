"""Read-only coordinator for UEM Shadow mode."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from .snapshot import StateSample, build_live_state

SHADOW_STATUS = "Shadow – keine aktive Steuerung"


@dataclass(frozen=True, slots=True)
class ShadowData:
    """All values published by the read-only Shadow coordinator."""

    status: str
    decision: str
    planned_charge_limit_w: float
    error: str | None

    @property
    def commands_sent(self) -> bool:
        """UEM's first release cannot send a command through this coordinator."""
        return False


class UemShadowCoordinator(DataUpdateCoordinator[ShadowData]):
    """Read source entities and publish a safe, explainable Shadow snapshot."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self._entry = entry

    async def _async_update_data(self) -> ShadowData:
        """Read live E3DC values only; never call a control service."""
        try:
            live = self._live_state()
        except ValueError as err:
            return ShadowData(
                status="Shadow – Messdatenfehler",
                decision="E3DC-Messwerte sind unvollständig oder ungültig; keine Steuerung aktiv.",
                planned_charge_limit_w=0.0,
                error=str(err),
            )

        return ShadowData(
            status=SHADOW_STATUS,
            decision=(
                f"Livewerte gültig (Akku {live.soc_pct:.0f} %); PV-Prognose ist noch nicht "
                "verbunden. UEM berechnet keine aktive Vorgabe."
            ),
            planned_charge_limit_w=0.0,
            error=None,
        )

    def _live_state(self):
        return build_live_state(
            now=dt_util.utcnow(),
            soc=self._sample(CONF_SOC_ENTITY),
            pv_power=self._sample(CONF_PV_POWER_ENTITY),
            house_power=self._sample(CONF_HOUSE_POWER_ENTITY),
            grid_export=self._sample(CONF_GRID_EXPORT_ENTITY),
            battery_charge=self._sample(CONF_BATTERY_CHARGE_ENTITY),
        )

    def _sample(self, config_key: str) -> StateSample:
        entity_id = self._entry.data.get(config_key)
        if not isinstance(entity_id, str):
            raise ValueError(f"missing configured entity for {config_key}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ValueError(f"unavailable source entity: {entity_id}")
        return StateSample(
            value=state.state,
            unit=state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            updated_at=state.last_updated,
        )
