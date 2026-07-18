from datetime import UTC, datetime, timedelta

import pytest

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)


def test_live_state_rejects_stale_measurements() -> None:
    with pytest.raises(ValueError, match="stale"):
        LiveState(
            timestamp=datetime(2026, 7, 18, 8, 0, tzinfo=UTC),
            now=datetime(2026, 7, 18, 8, 16, tzinfo=UTC),
            soc_pct=55.0,
            pv_power_w=3000.0,
            house_power_w=800.0,
            grid_export_w=500.0,
            battery_charge_w=1200.0,
        )


def test_live_state_rejects_measurements_from_the_future() -> None:
    now = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="future"):
        LiveState(
            timestamp=now.replace(minute=1),
            now=now,
            soc_pct=55.0,
            pv_power_w=3000.0,
            house_power_w=800.0,
            grid_export_w=500.0,
            battery_charge_w=1200.0,
        )


def test_live_state_rejects_non_finite_measurements() -> None:
    now = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="finite"):
        LiveState(
            timestamp=now,
            now=now,
            soc_pct=55.0,
            pv_power_w=float("nan"),
            house_power_w=800.0,
            grid_export_w=500.0,
            battery_charge_w=1200.0,
        )


def test_storage_capabilities_reject_non_finite_limits() -> None:
    with pytest.raises(ValueError, match="finite"):
        StorageCapabilities(usable_capacity_kwh=10.0, max_charge_power_w=float("inf"))


def test_forecast_point_rejects_non_finite_power() -> None:
    with pytest.raises(ValueError, match="finite"):
        ForecastPoint(
            start=datetime(2026, 7, 18, 8, 0, tzinfo=UTC),
            duration=timedelta(minutes=15),
            power_w=float("nan"),
        )


def test_planner_config_rejects_non_finite_target() -> None:
    with pytest.raises(ValueError, match="finite"):
        PlannerConfig(
            target_soc_pct=float("nan"),
            charge_end=datetime(2026, 7, 18, 18, 0, tzinfo=UTC),
        )
