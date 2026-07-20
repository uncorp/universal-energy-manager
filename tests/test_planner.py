from datetime import UTC, datetime, timedelta

from pytest import approx

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


def test_plan_charges_earlier_when_late_pv_forecast_deficit_exists() -> None:
    """Akzeptanzfall 2: geringe spätere PV-Prognose führt zu früherem/stärkerem Laden.

    Wenn die spätere PV-Prognose gering ist, muss der Planner im
    aktuellen Intervall einen höheren Ladeanteil setzen (über dem
    Durchschnitt), um das spätere PV-Loch auszugleichen.
    """
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    decision = plan_charge(
        live=LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=5000.0,
            house_power_w=500.0,
            grid_export_w=4500.0,
            battery_charge_w=0.0,
        ),
        storage=StorageCapabilities(
            usable_capacity_kwh=20.0,
            max_charge_power_w=12000.0,
        ),
        config=PlannerConfig(
            target_soc_pct=90.0,
            charge_end=now + timedelta(hours=2),
        ),
        forecast=(
            # Jetzt: 5000 W
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=5000.0),
            # Später: Einbruch auf 200 W
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(hours=1),
                power_w=200.0,
            ),
        ),
    )

    required_energy_kwh = 20.0 * (90.0 - 50.0) / 100.0  # 8 kWh
    assert decision.required_energy_kwh == approx(required_energy_kwh)
    # Later forecast: 0.2 kWh
    later_energy_kwh = 0.2
    energy_needed_now = max(0.0, required_energy_kwh - later_energy_kwh)  # 7.8 kWh
    power_needed_now = energy_needed_now * 3_600_000 / 3600  # 7800 W
    avg_power = required_energy_kwh * 3_600_000 / (2 * 3600)  # 4000 W
    available_surplus = 5000.0 - 500.0  # 4500 W
    expected_limit = min(12000.0, available_surplus, max(power_needed_now, avg_power))
    # min(12000, 4500, max(7800, 4000)) = min(12000, 4500, 7800) = 4500
    assert decision.charge_limit_w == approx(expected_limit)
    # Wichtig: Der Planner hat das späte PV-Loch erkannt und den
    # charge_limit auf power_needed_now (7800 W) gezogen –
    # begrenzt nur durch available_surplus_w (4500 W).
    # Ohne späten Deficit wäre avg_power=4000 W das Ergebnis.
    # Das Limit liegt über avg_power → früheres/stärkeres Laden.
    assert decision.charge_limit_w > avg_power
    assert "late-forecast shortfall" in decision.reason
