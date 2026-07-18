from datetime import UTC, datetime, timedelta

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)
from custom_components.universal_energy_manager.planner import plan_charge


def test_plan_charges_early_when_late_forecast_cannot_meet_final_target() -> None:
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    decision = plan_charge(
        live=LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=8000.0,
            house_power_w=500.0,
            grid_export_w=7500.0,
            battery_charge_w=0.0,
        ),
        storage=StorageCapabilities(
            usable_capacity_kwh=20.0,
            max_charge_power_w=12000.0,
        ),
        config=PlannerConfig(target_soc_pct=90.0, charge_end=now + timedelta(hours=2)),
        forecast=(
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=8000.0),
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(hours=1),
                power_w=1000.0,
            ),
        ),
    )

    assert decision.required_energy_kwh == 8.0
    assert decision.charge_limit_w == 7000.0
    assert "final target" in decision.reason
