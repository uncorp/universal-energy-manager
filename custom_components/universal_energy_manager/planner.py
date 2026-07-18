"""Pure daily charge planner."""

from __future__ import annotations

from collections.abc import Sequence

from .models import ChargeDecision, ForecastPoint, LiveState, PlannerConfig, StorageCapabilities


def _energy_kwh(point: ForecastPoint) -> float:
    return point.power_w * point.duration.total_seconds() / 3_600_000.0


def plan_charge(
    *,
    live: LiveState,
    storage: StorageCapabilities,
    config: PlannerConfig,
    forecast: Sequence[ForecastPoint],
) -> ChargeDecision:
    """Return a current charge limit aimed at the final target, not an interim target."""
    if config.charge_end <= live.now:
        raise ValueError("charge_end must be after now")

    required_energy_kwh = max(
        0.0,
        storage.usable_capacity_kwh * (config.target_soc_pct - live.soc_pct) / 100.0,
    )
    if required_energy_kwh == 0.0:
        return ChargeDecision(0.0, 0.0, "final target already reached")

    current_interval = next(
        (
            point
            for point in forecast
            if point.start <= live.now < point.start + point.duration
        ),
        None,
    )
    if current_interval is None:
        return ChargeDecision(
            required_energy_kwh,
            0.0,
            "no current forecast interval available for final target planning",
        )

    later_forecast_energy_kwh = sum(
        _energy_kwh(point)
        for point in forecast
        if point.start >= current_interval.start + current_interval.duration
        and point.start < config.charge_end
    )
    energy_needed_now_kwh = max(0.0, required_energy_kwh - later_forecast_energy_kwh)
    power_needed_now_w = (
        energy_needed_now_kwh * 3_600_000.0 / current_interval.duration.total_seconds()
    )
    average_power_needed_w = (
        required_energy_kwh
        * 3_600_000.0
        / (config.charge_end - live.now).total_seconds()
    )
    available_surplus_w = max(0.0, live.pv_power_w - live.house_power_w)
    charge_limit_w = min(
        storage.max_charge_power_w,
        available_surplus_w,
        max(power_needed_now_w, average_power_needed_w),
    )

    return ChargeDecision(
        required_energy_kwh=required_energy_kwh,
        charge_limit_w=charge_limit_w,
        reason="charging against final target with late-forecast shortfall considered",
    )
