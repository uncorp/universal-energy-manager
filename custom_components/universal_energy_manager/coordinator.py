"""Read-only coordinator for UEM Shadow mode."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_CHARGE_END,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    CONF_TARGET_SOC_PCT,
    DEFAULT_CHARGE_END_HOURS,
    DEFAULT_TARGET_SOC_PCT,
    DOMAIN,
)
from .forecast_solar import async_read_forecast_solar
from .models import ForecastPoint, LiveState, PlannerConfig, StorageCapabilities
from .planner import plan_charge
from .snapshot import StateSample, build_live_state

SHADOW_STATUS = "Shadow – keine aktive Steuerung"


@dataclass(frozen=True, slots=True)
class ShadowData:
    """All values published by the read-only Shadow coordinator."""

    status: str
    decision: str
    planned_charge_limit_w: float
    error: str | None
    forecast_connected: bool

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
        self._entry.async_on_unload(self.async_shutdown)

    async def _async_update_data(self) -> ShadowData:
        """Read live E3DC values only; never call a control service."""
        try:
            live = self._live_state()
        except ValueError as err:
            try:
                forecast_connected = await self._forecast_connected()
            except ValueError:
                forecast_connected = False
            return ShadowData(
                status="Shadow – Messdatenfehler",
                decision="E3DC-Messwerte sind unvollständig oder ungültig; keine Steuerung aktiv.",
                planned_charge_limit_w=0.0,
                error=str(err),
                forecast_connected=forecast_connected,
            )

        try:
            forecast = await self._forecast_connected()
        except ValueError as err:
            return ShadowData(
                status="Shadow – Prognosefehler",
                decision="PV-Prognose ist unvollständig oder ungültig; keine Steuerung aktiv.",
                planned_charge_limit_w=0.0,
                error=str(err),
                forecast_connected=False,
            )

        charge_limit_w = self._compute_charge_limit(live, forecast)

        return ShadowData(
            status=SHADOW_STATUS,
            decision=(
                f"Livewerte gültig (Akku {live.soc_pct:.0f} %); "
                f"{'PV-Prognose verbunden' if forecast else 'PV-Prognose noch nicht verbunden'}. "
                f"{'Berechne Ladevorgabe' if forecast else 'UEM berechnet keine aktive Vorgabe'}. "
                f"Soll-Ladelimit: {charge_limit_w:.0f} W."
            ),
            planned_charge_limit_w=charge_limit_w,
            error=None,
            forecast_connected=forecast,
        )

    async def _forecast_connected(self) -> bool:
        """Read configured cached forecast sources; never request a provider refresh."""
        entry_ids = self._entry.data.get(CONF_FORECAST_SOLAR_ENTRY_IDS)
        if entry_ids is not None:
            if not isinstance(entry_ids, list) or not all(
                isinstance(value, str) for value in entry_ids
            ):
                raise ValueError("invalid Forecast.Solar source configuration")
            if not entry_ids:
                return False
            return bool(await async_read_forecast_solar(self.hass, entry_ids))

        entity_id = self._entry.data.get(CONF_FORECAST_ENTITY)
        if not isinstance(entity_id, str):
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in {"unknown", "unavailable"}

    def _compute_charge_limit(self, live: LiveState, forecast_connected: bool) -> float:
        """Compute a Shadow-only charge limit via the pure planner."""
        try:
            storage = self._build_storage_capabilities()
            config = self._build_planner_config(live)
        except (ValueError, TypeError):
            return 0.0

        forecast: tuple[ForecastPoint, ...] = ()
        if forecast_connected:
            try:
                forecast = self._build_forecast_from_snapshot(live)
            except (ValueError, TypeError):
                forecast = ()

        try:
            decision = plan_charge(
                live=live,
                storage=storage,
                config=config,
                forecast=forecast,
            )
            return decision.charge_limit_w
        except ValueError:
            return 0.0

    def _build_storage_capabilities(self) -> StorageCapabilities:
        """Derive storage limits from configured entities."""
        cap_entity = self._entry.data.get(CONF_BATTERY_CAPACITY_ENTITY)
        max_entity = self._entry.data.get(CONF_MAX_CHARGE_POWER_ENTITY)

        cap_val = self._parse_float_entity(cap_entity)
        max_val = self._parse_float_entity(max_entity)

        if cap_val is None or max_val is None:
            raise ValueError("missing battery capacity or max charge power")

        return StorageCapabilities(
            usable_capacity_kwh=float(cap_val),
            max_charge_power_w=float(max_val),
        )

    def _parse_float_entity(self, entity_id: str | None) -> float | None:
        """Best-effort float from a configured entity state, or None."""
        if not isinstance(entity_id, str):
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _resolve_charge_end(self, live: LiveState) -> datetime:
        """Derive charge_end from entry data or fall back to defaults."""
        charge_end_raw = self._entry.data.get(CONF_CHARGE_END)
        if isinstance(charge_end_raw, str):
            try:
                charge_end = datetime.fromisoformat(charge_end_raw)
            except (TypeError, ValueError):
                charge_end = live.now + timedelta(hours=DEFAULT_CHARGE_END_HOURS)
        else:
            charge_end = live.now + timedelta(hours=DEFAULT_CHARGE_END_HOURS)

        if charge_end.tzinfo is None:
            charge_end = charge_end.replace(tzinfo=live.now.tzinfo)
        return charge_end

    def _build_planner_config(self, live: LiveState) -> PlannerConfig:
        """Derive PlannerConfig from entry data with safe defaults."""
        target_soc = self._entry.data.get(CONF_TARGET_SOC_PCT)
        if not isinstance(target_soc, (int, float)):
            target_soc = DEFAULT_TARGET_SOC_PCT

        return PlannerConfig(
            target_soc_pct=float(target_soc),
            charge_end=self._resolve_charge_end(live),
        )

    def _build_forecast_from_snapshot(self, live: LiveState) -> tuple[ForecastPoint, ...]:
        """Build a minimal forecast from the current PV state for the
        Shadow planner when no Forecast.Solar data is available.

        Uses the current PV power as a single interval
        ending at charge_end. This ensures the planner can make a
        meaningful decision even when only live PV data is available.
        """
        pv_power = live.pv_power_w
        if pv_power <= 0:
            return ()

        charge_end = self._resolve_charge_end(live)

        return (ForecastPoint(
            start=live.now,
            duration=charge_end - live.now,
            power_w=pv_power,
        ),)

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
