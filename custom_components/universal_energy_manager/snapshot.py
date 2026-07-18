"""Translate Home Assistant entity state values into planner input models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import LiveState
from .normalization import power_to_w


@dataclass(frozen=True, slots=True)
class StateSample:
    """The value, unit and update time of one required source measurement."""

    value: str | int | float
    unit: str | None
    updated_at: datetime


def _percent(sample: StateSample) -> float:
    if sample.unit not in {None, "%"}:
        raise ValueError(f"unsupported state-of-charge unit: {sample.unit}")
    try:
        return float(sample.value)
    except (TypeError, ValueError) as err:
        raise ValueError("state of charge is not numeric") from err


def build_live_state(
    *,
    now: datetime,
    soc: StateSample,
    pv_power: StateSample,
    house_power: StateSample,
    grid_export: StateSample,
    battery_charge: StateSample,
) -> LiveState:
    """Build a validated live-state snapshot using the oldest source timestamp."""
    samples = (soc, pv_power, house_power, grid_export, battery_charge)
    return LiveState(
        timestamp=min(sample.updated_at for sample in samples),
        now=now,
        soc_pct=_percent(soc),
        pv_power_w=power_to_w(pv_power.value, pv_power.unit),
        house_power_w=power_to_w(house_power.value, house_power.unit),
        grid_export_w=power_to_w(grid_export.value, grid_export.unit),
        battery_charge_w=power_to_w(battery_charge.value, battery_charge.unit),
    )
