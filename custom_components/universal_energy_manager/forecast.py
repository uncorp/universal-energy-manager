"""Local, source-neutral 15-minute production forecast helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from .models import ForecastPoint


def combine_producer_forecasts(
    producer_forecasts: Sequence[Sequence[ForecastPoint]],
) -> tuple[ForecastPoint, ...]:
    """Sum individually forecasted generators by their exact time interval."""
    power_by_interval: dict[tuple[datetime, timedelta], float] = {}
    for forecast in producer_forecasts:
        for point in forecast:
            key = (point.start, point.duration)
            power_by_interval[key] = power_by_interval.get(key, 0.0) + point.power_w

    return tuple(
        ForecastPoint(start=start, duration=duration, power_w=power_w)
        for (start, duration), power_w in sorted(power_by_interval.items())
    )


def forecast_from_hourly_energy(
    wh_hours: dict[str, float | int],
) -> tuple[ForecastPoint, ...]:
    """Translate hourly energy dicts (Forecast.Solar style) into forecast points."""
    points: list[ForecastPoint] = []
    for timestamp, energy_wh in wh_hours.items():
        try:
            start = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError) as err:
            raise ValueError(f"invalid forecast timestamp: {timestamp}") from err
        if start.tzinfo is None:
            raise ValueError("forecast timestamps must be timezone-aware")
        if energy_wh < 0:
            raise ValueError("forecast energy must be non-negative")
        points.append(
            ForecastPoint(
                start=start,
                duration=timedelta(hours=1),
                power_w=float(energy_wh),
            )
        )
    return tuple(sorted(points, key=lambda p: p.start))


def forecast_from_minute_data(
    minute_data: dict[str, float | int],
) -> tuple[ForecastPoint, ...]:
    """Translate 15-minute resolution energy dicts into forecast points."""
    points: list[ForecastPoint] = []
    for timestamp, energy_wh in minute_data.items():
        try:
            start = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError) as err:
            raise ValueError(f"invalid forecast timestamp: {timestamp}") from err
        if start.tzinfo is None:
            raise ValueError("forecast timestamps must be timezone-aware")
        if energy_wh < 0:
            raise ValueError("forecast energy must be non-negative")
        points.append(
            ForecastPoint(
                start=start,
                duration=timedelta(minutes=15),
                power_w=float(energy_wh) * 4,  # wh to average w over 15 min
            )
        )
    return tuple(sorted(points, key=lambda p: p.start))
