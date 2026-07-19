"""Adapter for cached Home Assistant Forecast.Solar production curves."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from .forecast import combine_producer_forecasts
from .models import ForecastPoint

_HOURLY_INTERVAL = timedelta(hours=1)


def forecast_points_from_wh_hours(
    wh_hours: Mapping[str, float | int],
) -> tuple[ForecastPoint, ...]:
    """Translate Forecast.Solar's cached hourly energy data into forecast points.

    The provider supplies watt-hours per hour. UEM preserves this hourly source
    resolution rather than fabricating quarter-hour peaks.
    """
    points: list[ForecastPoint] = []
    for timestamp, energy_wh in wh_hours.items():
        start = datetime.fromisoformat(timestamp)
        if start.tzinfo is None:
            raise ValueError("Forecast timestamps must be timezone-aware")
        if energy_wh < 0:
            raise ValueError("Forecast energy must be non-negative")
        points.append(
            ForecastPoint(
                start=start,
                duration=_HOURLY_INTERVAL,
                power_w=float(energy_wh),
            )
        )
    return tuple(sorted(points, key=lambda point: point.start))


ForecastSolarFetcher = Callable[[Any, str], Awaitable[Mapping[str, Any] | None]]


async def async_read_forecast_solar(
    hass: Any,
    config_entry_ids: Sequence[str],
    *,
    fetch: ForecastSolarFetcher | None = None,
) -> tuple[ForecastPoint, ...]:
    """Read cached Forecast.Solar curves without making a network request.

    The HA Forecast.Solar energy helper reads its already refreshed coordinator
    state. A missing configured source invalidates the aggregate instead of
    silently planning against incomplete production data.
    """
    if fetch is None:
        from homeassistant.components.forecast_solar.energy import (
            async_get_solar_forecast,
        )

        fetch = async_get_solar_forecast

    assert fetch is not None
    curves: list[tuple[ForecastPoint, ...]] = []
    for config_entry_id in config_entry_ids:
        forecast = await fetch(hass, config_entry_id)
        if forecast is None:
            raise ValueError("configured Forecast.Solar source is unavailable")
        if not isinstance(forecast, Mapping):
            raise ValueError("Forecast.Solar source returned no hourly curve")
        wh_hours = forecast.get("wh_hours")
        if not isinstance(wh_hours, Mapping):
            raise ValueError("Forecast.Solar source returned no hourly curve")
        curves.append(forecast_points_from_wh_hours(wh_hours))

    return combine_producer_forecasts(curves)
