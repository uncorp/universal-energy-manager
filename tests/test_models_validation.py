"""Tests for remaining uncovered validation paths in models.py.

Covers:
- LiveState line 24: non-timezone-aware timestamp
- LiveState line 26: future timestamp
- ForecastPoint line 62: non-timezone-aware start
- ForecastPoint line 64: zero/negative duration
- StorageCapabilities line 80: non-finite values
- PlannerConfig line 100: non-timezone-aware charge_end
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import inf, nan

import pytest

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)


class TestLiveStateMissingTzinfo:
    """Uncovered: LiveState line 24 — non-timezone-aware timestamp."""

    def test_rejects_naive_timestamp(self) -> None:
        """LiveState must reject a timezone-naive timestamp."""
        naive = datetime(2026, 7, 18, 10, 0)  # no tzinfo
        with pytest.raises(ValueError, match="timezone-aware"):
            LiveState(
                timestamp=naive,
                now=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
                soc_pct=50.0,
                pv_power_w=3000.0,
                house_power_w=1000.0,
                grid_export_w=2000.0,
                battery_charge_w=0.0,
            )

    def test_rejects_naive_now(self) -> None:
        """LiveState must reject a timezone-naive `now`."""
        with pytest.raises(ValueError, match="timezone-aware"):
            LiveState(
                timestamp=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
                now=datetime(2026, 7, 18, 10, 0),  # no tzinfo
                soc_pct=50.0,
                pv_power_w=3000.0,
                house_power_w=1000.0,
                grid_export_w=2000.0,
                battery_charge_w=0.0,
            )


class TestLiveStateFutureTimestamp:
    """Uncovered: LiveState line 26 — timestamp in the future."""

    def test_rejects_future_timestamp(self) -> None:
        """LiveState must reject a timestamp that is after `now`."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        future = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="not be from the future"):
            LiveState(
                timestamp=future,
                now=now,
                soc_pct=50.0,
                pv_power_w=3000.0,
                house_power_w=1000.0,
                grid_export_w=2000.0,
                battery_charge_w=0.0,
            )


class TestForecastPointMissingTzinfo:
    """Uncovered: ForecastPoint line 62 — non-timezone-aware start."""

    def test_rejects_naive_start(self) -> None:
        """ForecastPoint must reject a timezone-naive start datetime."""
        naive = datetime(2026, 7, 18, 10, 0)  # no tzinfo
        with pytest.raises(ValueError, match="timezone-aware"):
            ForecastPoint(start=naive, duration=timedelta(minutes=15), power_w=3000.0)


class TestForecastPointZeroDuration:
    """Uncovered: ForecastPoint line 64 — zero or negative duration."""

    def test_rejects_zero_duration(self) -> None:
        """ForecastPoint must reject a zero-duration interval."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="positive"):
            ForecastPoint(start=now, duration=timedelta(seconds=0), power_w=3000.0)

    def test_rejects_negative_duration(self) -> None:
        """ForecastPoint must reject a negative-duration interval."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="positive"):
            ForecastPoint(start=now, duration=timedelta(minutes=-15), power_w=3000.0)


class TestStorageCapabilitiesNonfinite:
    """Uncovered: StorageCapabilities line 80 — non-finite values."""

    def test_rejects_infinite_capacity(self) -> None:
        """StorageCapabilities must reject infinite usable_capacity_kwh."""
        with pytest.raises(ValueError, match="finite"):
            StorageCapabilities(usable_capacity_kwh=inf, max_charge_power_w=5000.0)

    def test_rejects_nan_capacity(self) -> None:
        """StorageCapabilities must reject NaN usable_capacity_kwh."""
        with pytest.raises(ValueError, match="finite"):
            StorageCapabilities(usable_capacity_kwh=nan, max_charge_power_w=5000.0)

    def test_rejects_infinite_max_charge(self) -> None:
        """StorageCapabilities must reject infinite max_charge_power_w."""
        with pytest.raises(ValueError, match="finite"):
            StorageCapabilities(usable_capacity_kwh=10.0, max_charge_power_w=inf)

    def test_rejects_nan_max_charge(self) -> None:
        """StorageCapabilities must reject NaN max_charge_power_w."""
        with pytest.raises(ValueError, match="finite"):
            StorageCapabilities(usable_capacity_kwh=10.0, max_charge_power_w=nan)


class TestPlannerConfigMissingTzinfo:
    """Uncovered: PlannerConfig line 100 — non-timezone-aware charge_end."""

    def test_rejects_naive_charge_end(self) -> None:
        """PlannerConfig must reject a timezone-naive charge_end."""
        naive = datetime(2026, 7, 18, 20, 0)  # no tzinfo
        with pytest.raises(ValueError, match="timezone-aware"):
            PlannerConfig(target_soc_pct=80.0, charge_end=naive)
