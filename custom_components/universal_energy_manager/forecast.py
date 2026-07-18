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
