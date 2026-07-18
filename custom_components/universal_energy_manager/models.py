"""Pure planning models for UEM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
