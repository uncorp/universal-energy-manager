"""Conditional free-storage headroom for expected curtailment."""

from __future__ import annotations

from collections.abc import Sequence

from .models import ForecastPoint


def calculate_headroom_kwh(
    *,
    forecast: Sequence[ForecastPoint],
    export_limit_w: float | None,
    expected_base_load_w: float,
    planned_flexible_load_w: float,
    max_charge_power_w: float,
) -> float:
    """Return forecast energy that needs free storage to avoid likely curtailment."""
    if export_limit_w is None:
        return 0.0
    if export_limit_w < 0.0:
        raise ValueError("export_limit_w must be non-negative")
    if expected_base_load_w < 0.0 or planned_flexible_load_w < 0.0:
        raise ValueError("expected loads must be non-negative")
    if max_charge_power_w <= 0.0:
        raise ValueError("max_charge_power_w must be positive")

    headroom_kwh = 0.0
    for point in forecast:
        excess_w = max(
            0.0,
            point.power_w
            - expected_base_load_w
            - planned_flexible_load_w
            - export_limit_w,
        )
        absorbable_w = min(excess_w, max_charge_power_w)
        headroom_kwh += absorbable_w * point.duration.total_seconds() / 3_600_000.0
    return headroom_kwh
