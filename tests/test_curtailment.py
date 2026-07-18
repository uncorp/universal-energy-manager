"""Regression tests for curtailment headroom edge cases."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.universal_energy_manager.curtailment import calculate_headroom_kwh
from custom_components.universal_energy_manager.models import ForecastPoint


def test_headroom_is_zero_when_export_limit_is_none() -> None:
    """When export_limit_w is None (no export limit set),
    the function must return 0.0 — no headroom calculation needed."""
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            ForecastPoint(start=now, duration=timedelta(hours=2), power_w=10000.0),
        ),
        export_limit_w=None,
        expected_base_load_w=500.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=12000.0,
    )
    assert headroom == 0.0


def test_headroom_is_zero_when_forecast_is_empty() -> None:
    """An empty forecast must return zero headroom, not crash."""
    headroom = calculate_headroom_kwh(
        forecast=(),
        export_limit_w=6000.0,
        expected_base_load_w=500.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=12000.0,
    )
    assert headroom == 0.0


def test_headroom_respects_export_limit_cap() -> None:
    """When surplus is below the export limit, no headroom is needed."""
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            # Power is only 3000, export limit is 6000, base load is 500
            # Excess = max(0, 3000 - 500 - 0 - 6000) = 0
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=3000.0),
        ),
        export_limit_w=6000.0,
        expected_base_load_w=500.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=12000.0,
    )
    assert headroom == 0.0


def test_headroom_capped_by_max_charge_power() -> None:
    """When excess exceeds max_charge_power, headroom is capped."""
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            # Excess = 10000 - 500 - 0 - 6000 = 3500
            # Absorbable = min(3500, 12000) = 3500
            # Headroom = 3500 * 3600000 / 3600000 = 3500 Wh = 3.5 kWh
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=10000.0),
        ),
        export_limit_w=6000.0,
        expected_base_load_w=500.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=12000.0,
    )
    assert headroom == 3.5


def test_headroom_capped_when_max_charge_power_larger_than_excess() -> None:
    """When max_charge_power exceeds excess, absorbable = excess."""
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            # Excess = 8000 - 500 - 0 - 6000 = 1500
            # Absorbable = min(1500, 5000) = 1500
            # Headroom = 1500 * 3600000 / 3600000 = 1.5 kWh
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=8000.0),
        ),
        export_limit_w=6000.0,
        expected_base_load_w=500.0,
        planned_flexible_load_w=0.0,
        max_charge_power_w=5000.0,
    )
    assert headroom == 1.5


def test_headroom_includes_planned_flexible_load() -> None:
    """Planned flexible load reduces available headroom for charging."""
    now = datetime(2026, 7, 18, 11, 0, tzinfo=UTC)
    headroom = calculate_headroom_kwh(
        forecast=(
            # Excess = 10000 - 500 - 2000 - 6000 = 1500
            # Absorbable = min(1500, 12000) = 1500
            # Headroom = 1500 * 3600000 / 3600000 = 1.5 kWh
            ForecastPoint(start=now, duration=timedelta(hours=1), power_w=10000.0),
        ),
        export_limit_w=6000.0,
        expected_base_load_w=500.0,
        planned_flexible_load_w=2000.0,
        max_charge_power_w=12000.0,
    )
    assert headroom == 1.5


def test_headroom_rejects_negative_export_limit() -> None:
    """Negative export_limit must raise ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_headroom_kwh(
            forecast=(),
            export_limit_w=-1.0,
            expected_base_load_w=0.0,
            planned_flexible_load_w=0.0,
            max_charge_power_w=1000.0,
        )


def test_headroom_rejects_negative_base_load() -> None:
    """Negative expected_base_load must raise ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_headroom_kwh(
            forecast=(),
            export_limit_w=6000.0,
            expected_base_load_w=-1.0,
            planned_flexible_load_w=0.0,
            max_charge_power_w=1000.0,
        )


def test_headroom_rejects_negative_flexible_load() -> None:
    """Negative planned_flexible_load must raise ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_headroom_kwh(
            forecast=(),
            export_limit_w=6000.0,
            expected_base_load_w=0.0,
            planned_flexible_load_w=-1.0,
            max_charge_power_w=1000.0,
        )


def test_headroom_rejects_non_positive_max_charge_power() -> None:
    """Non-positive max_charge_power must raise ValueError."""
    with pytest.raises(ValueError, match="positive"):
        calculate_headroom_kwh(
            forecast=(),
            export_limit_w=6000.0,
            expected_base_load_w=0.0,
            planned_flexible_load_w=0.0,
            max_charge_power_w=0.0,
        )
