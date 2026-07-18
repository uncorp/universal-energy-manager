"""Regression test: plan_charge returns zero limit when no forecast covers ``now``."""

from datetime import UTC, datetime, timedelta

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)
from custom_components.universal_energy_manager.planner import plan_charge


def _make_live(now: datetime) -> LiveState:
    return LiveState(
        timestamp=now,
        now=now,
        soc_pct=40.0,
        pv_power_w=2000.0,
        house_power_w=1000.0,
        grid_export_w=1000.0,
        battery_charge_w=0.0,
    )


def _make_storage() -> StorageCapabilities:
    return StorageCapabilities(usable_capacity_kwh=20.0, max_charge_power_w=12000.0)


def _make_config(now: datetime) -> PlannerConfig:
    return PlannerConfig(target_soc_pct=80.0, charge_end=now + timedelta(hours=4))


def test_plan_charge_returns_zero_when_forecast_starts_after_now() -> None:
    """If the earliest forecast interval begins after ``now``, the planner cannot
    anchor a charge-limit and must return zero — never guessing a limit."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    decision = plan_charge(
        live=_make_live(now),
        storage=_make_storage(),
        config=_make_config(now),
        forecast=(
            # Forecast starts 30 minutes *after* now — no interval covers now.
            ForecastPoint(
                start=now + timedelta(minutes=30),
                duration=timedelta(minutes=15),
                power_w=5000.0,
            ),
        ),
    )

    assert decision.charge_limit_w == 0.0
    assert "no current forecast" in decision.reason.lower()


def test_plan_charge_returns_zero_when_forecast_is_completely_before_now() -> None:
    """A forecast entirely in the past must also yield a zero limit."""
    now = datetime(2026, 7, 18, 14, 0, tzinfo=UTC)

    decision = plan_charge(
        live=_make_live(now),
        storage=_make_storage(),
        config=_make_config(now),
        forecast=(
            ForecastPoint(
                start=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
                duration=timedelta(hours=1),
                power_w=6000.0,
            ),
        ),
    )

    assert decision.charge_limit_w == 0.0
    assert "no current forecast" in decision.reason.lower()


def test_plan_charge_returns_zero_when_forecast_is_completely_in_future() -> None:
    """A forecast that starts well after now (gap > duration) yields zero."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    decision = plan_charge(
        live=_make_live(now),
        storage=_make_storage(),
        config=_make_config(now),
        forecast=(
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(minutes=15),
                power_w=3000.0,
            ),
        ),
    )

    assert decision.charge_limit_w == 0.0
    assert "no current forecast" in decision.reason.lower()
