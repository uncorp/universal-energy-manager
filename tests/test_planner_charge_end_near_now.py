"""Test plan_charge with a charge_end close to now."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)
from custom_components.universal_energy_manager.planner import plan_charge


def test_plan_charge_raises_when_charge_end_before_now() -> None:
    """plan_charge must reject a charge_end in the past."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="charge_end"):
        plan_charge(
            live=LiveState(
                timestamp=now,
                now=now,
                soc_pct=40.0,
                pv_power_w=5000.0,
                house_power_w=500.0,
                grid_export_w=4500.0,
                battery_charge_w=0.0,
            ),
            storage=StorageCapabilities(usable_capacity_kwh=20.0, max_charge_power_w=12000.0),
            config=PlannerConfig(target_soc_pct=80.0, charge_end=now - timedelta(hours=1)),
            forecast=(ForecastPoint(start=now, duration=timedelta(minutes=15), power_w=5000.0),),
        )


def test_plan_charge_respects_max_charge_power_cap() -> None:
    """The planner must never return a charge_limit exceeding max_charge_power_w."""
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    decision = plan_charge(
        live=LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=15000.0,
            house_power_w=500.0,
            grid_export_w=14500.0,
            battery_charge_w=0.0,
        ),
        storage=StorageCapabilities(usable_capacity_kwh=20.0, max_charge_power_w=12000.0),
        config=PlannerConfig(target_soc_pct=90.0, charge_end=now + timedelta(hours=2)),
        forecast=(
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=15000.0),
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(hours=1),
                power_w=2000.0,
            ),
        ),
    )
    assert decision.charge_limit_w <= 12000.0


def test_plan_charge_zero_limit_when_target_already_reached() -> None:
    """If SoC >= target_soc_pct, required_energy_kwh is zero and limit is zero."""
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    decision = plan_charge(
        live=LiveState(
            timestamp=now,
            now=now,
            soc_pct=95.0,
            pv_power_w=3000.0,
            house_power_w=500.0,
            grid_export_w=2500.0,
            battery_charge_w=0.0,
        ),
        storage=StorageCapabilities(usable_capacity_kwh=20.0, max_charge_power_w=12000.0),
        config=PlannerConfig(target_soc_pct=90.0, charge_end=now + timedelta(hours=4)),
        forecast=(ForecastPoint(start=now, duration=timedelta(hours=4), power_w=3000.0),),
    )
    assert decision.required_energy_kwh == 0.0
    assert decision.charge_limit_w == 0.0
    assert "already reached" in decision.reason


def test_plan_charge_respects_available_surplus() -> None:
    """The planner must not request more charge than available PV surplus."""
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    decision = plan_charge(
        live=LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=3000.0,
            house_power_w=500.0,
            grid_export_w=2500.0,
            battery_charge_w=0.0,
        ),
        storage=StorageCapabilities(usable_capacity_kwh=20.0, max_charge_power_w=12000.0),
        config=PlannerConfig(target_soc_pct=90.0, charge_end=now + timedelta(hours=2)),
        forecast=(
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=3000.0),
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(hours=1),
                power_w=1000.0,
            ),
        ),
    )
    available_surplus = 3000.0 - 500.0  # 2500 W
    assert decision.charge_limit_w <= available_surplus
