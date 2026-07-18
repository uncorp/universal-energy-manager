"""Pure planning models for UEM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class LiveState:
    """Normalized live measurements required by the planner."""

    timestamp: datetime
    now: datetime
    soc_pct: float
    pv_power_w: float
    house_power_w: float
    grid_export_w: float
    battery_charge_w: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.now.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if (self.now - self.timestamp).total_seconds() > 15 * 60:
            raise ValueError("stale live measurements")
        if not 0.0 <= self.soc_pct <= 100.0:
            raise ValueError("soc_pct must be between 0 and 100")
        if self.pv_power_w < 0.0:
            raise ValueError("pv_power_w must be non-negative")
        if self.house_power_w < 0.0:
            raise ValueError("house_power_w must be non-negative")


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """Forecasted power for one contiguous time interval."""

    start: datetime
    duration: timedelta
    power_w: float

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError("forecast timestamp must be timezone-aware")
        if self.duration.total_seconds() <= 0:
            raise ValueError("forecast duration must be positive")
        if self.power_w < 0.0:
            raise ValueError("forecast power must be non-negative")


@dataclass(frozen=True, slots=True)
class StorageCapabilities:
    """Sustained storage limits relevant to a short-horizon charge decision."""

    usable_capacity_kwh: float
    max_charge_power_w: float

    def __post_init__(self) -> None:
        if self.usable_capacity_kwh <= 0.0:
            raise ValueError("usable_capacity_kwh must be positive")
        if self.max_charge_power_w <= 0.0:
            raise ValueError("max_charge_power_w must be positive")


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    """User-visible daily charging goal."""

    target_soc_pct: float
    charge_end: datetime

    def __post_init__(self) -> None:
        if not 0.0 <= self.target_soc_pct <= 100.0:
            raise ValueError("target_soc_pct must be between 0 and 100")
        if self.charge_end.tzinfo is None:
            raise ValueError("charge_end must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ChargeDecision:
    """A pure planner result with an explainable requested charge limit."""

    required_energy_kwh: float
    charge_limit_w: float
    reason: str
