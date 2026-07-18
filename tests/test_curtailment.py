from datetime import UTC, datetime, timedelta

from custom_components.universal_energy_manager.curtailment import calculate_headroom_kwh
from custom_components.universal_energy_manager.models import ForecastPoint


def test_headroom_reserves_only_energy_above_export_limit() -> None:
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=8000.0),
            ForecastPoint(
                start=now + timedelta(hours=1),
                duration=timedelta(hours=1),
                power_w=10000.0,
            ),
        ),
        export_limit_w=6000.0,
        expected_base_load_w=1000.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=12000.0,
    )

    assert headroom == 4.0
