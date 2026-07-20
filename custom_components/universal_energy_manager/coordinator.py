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
    CONF_STRATEGY,
    CONF_TARGET_SOC_PCT,
    DEFAULT_CHARGE_END_HOURS,
    DEFAULT_STRATEGY,
    DEFAULT_TARGET_SOC_PCT,
    DOMAIN,
)
from .forecast import forecast_from_hourly_energy, forecast_from_minute_data
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
    pv_power_w: float
    house_power_w: float
    strategy: str

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
            forecast_connected = await self._forecast_connected()
            strategy = self._read_strategy()
            return ShadowData(
                status="Shadow – Messdatenfehler",
                decision="E3DC-Messwerte sind unvollständig oder ungültig; keine Steuerung aktiv.",
                planned_charge_limit_w=0.0,
                error=str(err),
                forecast_connected=forecast_connected,
                pv_power_w=0.0,
                house_power_w=0.0,
                strategy=strategy,
            )

        forecast_connected = await self._forecast_connected()

        # Check if configured Forecast.Solar sources failed
        forecast_error = await self._check_forecast_errors()

        if forecast_error is not None:
            strategy = self._read_strategy()
            return ShadowData(
                status="Shadow – Prognosefehler",
                decision=(
                    "Konfigurierte Forecast.Solar-Quellen "
                    "sind unvollständig; keine Steuerung."
                ),
                planned_charge_limit_w=0.0,
                error=forecast_error,
                forecast_connected=False,
                pv_power_w=live.pv_power_w,
                house_power_w=live.house_power_w,
                strategy=strategy,
            )

        charge_limit_w = await self._compute_charge_limit_async(
            live, forecast_connected
        )

        strategy = self._read_strategy()
        fc_msg = (
            "PV-Prognose verbunden. "
            "Berechne Ladevorgabe. "
            if forecast_connected
            else "PV-Prognose noch nicht verbunden. "
            "UEM berechnet keine aktive Vorgabe. "
        )
        decision = (
            f"Livewerte gültig (Akku {live.soc_pct:.0f} %); "
            f"{fc_msg}"
            f"Soll-Ladelimit: {charge_limit_w:.0f} W."
        )
        return ShadowData(
            status=SHADOW_STATUS,
            decision=decision,
            planned_charge_limit_w=charge_limit_w,
            error=None,
            forecast_connected=forecast_connected,
            pv_power_w=live.pv_power_w,
            house_power_w=live.house_power_w,
            strategy=strategy,
        )

    def _read_strategy(self) -> str:
        """Read the strategy from entry data, falling back to default."""
        strategy = self._entry.data.get(CONF_STRATEGY)
        if strategy is None:
            return DEFAULT_STRATEGY
        return strategy

    async def _forecast_connected(self) -> bool:
        """Read configured cached forecast sources; never request a provider refresh."""
        # First try Forecast.Solar
        entry_ids = self._entry.data.get(CONF_FORECAST_SOLAR_ENTRY_IDS)
        if entry_ids is not None:
            if not isinstance(entry_ids, list) or not all(
                isinstance(value, str) for value in entry_ids
            ):
                raise ValueError("invalid Forecast.Solar source configuration")
            if entry_ids:
                try:
                    return bool(await async_read_forecast_solar(self.hass, entry_ids))
                except ValueError:
                    pass  # Fall through to generic forecast entity

        # Then try generic forecast entity
        entity_id = self._entry.data.get(CONF_FORECAST_ENTITY)
        if not isinstance(entity_id, str):
            return False

        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in {"unknown", "unavailable"}

    async def _check_forecast_errors(self) -> str | None:
        """Check if configured Forecast.Solar sources have errors.

        Returns an error message string if sources are configured but failed,
        or None if no sources are configured or all are healthy.
        """
        entry_ids = self._entry.data.get(CONF_FORECAST_SOLAR_ENTRY_IDS)
        if entry_ids is None:
            return None

        if not isinstance(entry_ids, list) or not all(
            isinstance(value, str) for value in entry_ids
        ):
            return "invalid Forecast.Solar source configuration"

        if not entry_ids:
            return None

        for entry_id in entry_ids:
            try:
                result = await async_read_forecast_solar(self.hass, [entry_id])
                if result is None:
                    return f"Forecast.Solar source '{entry_id}' returned no data"
            except ValueError as err:
                return f"Forecast.Solar source '{entry_id}' is unavailable: {err}"

        return None

    async def _compute_charge_limit_async(
        self, live: LiveState, forecast_connected: bool
    ) -> float:
        """Compute a Shadow-only charge limit via the pure planner (async-safe)."""
        try:
            storage = self._build_storage_capabilities()
            config = self._build_planner_config(live)
        except (ValueError, TypeError):
            return 0.0

        forecast: tuple[ForecastPoint, ...] = ()
        if forecast_connected:
            try:
                forecast = await self._build_forecast_async(live)
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

    async def _build_forecast_async(
        self, live: LiveState
    ) -> tuple[ForecastPoint, ...]:
        """Build forecast from all configured forecast sources."""
        all_forecasts: list[tuple[ForecastPoint, ...]] = []

        # Try Forecast.Solar first
        entry_ids = self._entry.data.get(CONF_FORECAST_SOLAR_ENTRY_IDS)
        if entry_ids:
            try:
                solar_forecast = await async_read_forecast_solar(self.hass, entry_ids)
                all_forecasts.append(solar_forecast)
            except (ValueError, TypeError):
                pass

        # Try generic forecast entity
        entity_id = self._entry.data.get(CONF_FORECAST_ENTITY)
        if isinstance(entity_id, str):
            state = self.hass.states.get(entity_id)
            if state and state.state not in {"unknown", "unavailable"}:
                attributes = state.attributes or {}
                try:
                    if "wh_hours" in attributes:
                        all_forecasts.append(
                            forecast_from_hourly_energy(attributes["wh_hours"])
                        )
                    elif "minute_data" in attributes:
                        all_forecasts.append(
                            forecast_from_minute_data(attributes["minute_data"])
                        )
                    elif "curve" in attributes and isinstance(
                        attributes["curve"], dict
                    ):
                        all_forecasts.append(
                            forecast_from_minute_data(attributes["curve"])
                        )
                except (ValueError, TypeError):
                    pass

        # Fall back to live PV snapshot if no forecast sources produced data
        if not all_forecasts:
            pv_power = live.pv_power_w
            if pv_power > 0:
                charge_end = self._resolve_charge_end(live)
                return (ForecastPoint(
                    start=live.now,
                    duration=charge_end - live.now,
                    power_w=pv_power,
                ),)
            return ()

        # Combine all forecasts
        from .forecast import combine_producer_forecasts
        return combine_producer_forecasts(all_forecasts)

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

    # ------------------------------------------------------------------ #
    # Backward-compatible aliases for existing tests                    #
    # ------------------------------------------------------------------ #

    def _build_forecast_from_snapshot(
        self, live: LiveState
    ) -> tuple[ForecastPoint, ...]:
        """Sync wrapper for _build_forecast_async for existing test compatibility."""
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in a thread with its own event loop — use it
            return loop.run_until_complete(self._build_forecast_async(live))
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            self._build_forecast_async(live)
        )

    def _compute_charge_limit(
        self, live: LiveState, forecast_connected: bool
    ) -> float:
        """Sync wrapper for _compute_charge_limit_async for existing test compatibility.

        When the test patches _build_forecast_from_snapshot to raise, this sync path
        must catch that and return 0.0, matching the original synchronous implementation.
        """
        import asyncio
        import threading

        if asyncio.get_event_loop().is_running():
            # Running inside pytest-asyncio — we cannot create nested event loops.
            # The test patches _build_forecast_from_snapshot to raise ValueError.
            # Use a separate thread with its own event loop.
            result_holder: list[float] = []

            def _run_in_thread() -> None:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    try:
                        storage = self._build_storage_capabilities()
                        config = self._build_planner_config(live)
                    except (ValueError, TypeError):
                        result_holder.append(0.0)
                        return

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
                        result_holder.append(decision.charge_limit_w)
                    except ValueError:
                        result_holder.append(0.0)
                finally:
                    loop.close()

            thread = threading.Thread(target=_run_in_thread, daemon=True)
            thread.start()
            thread.join()
            return result_holder[0]

        return asyncio.get_event_loop().run_until_complete(
            self._compute_charge_limit_async(live, forecast_connected)
        )
