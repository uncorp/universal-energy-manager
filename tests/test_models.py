"""Tests for pure planning models validation."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.universal_energy_manager.models import (
    ForecastPoint,
    LiveState,
    PlannerConfig,
    StorageCapabilities,
)


class TestLiveStateValidation:
    """Tests for LiveState input validation."""

    def _make_base(self, **overrides) -> dict:
        """Base kwargs with timezone-aware timestamps."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        base = {
            "timestamp": now,
            "now": now,
            "soc_pct": 50.0,
            "pv_power_w": 3000.0,
            "house_power_w": 1000.0,
            "grid_export_w": 2000.0,
            "battery_charge_w": 0.0,
        }
        base.update(overrides)
        return base

    def test_rejects_nonfinite_soc_pct(self) -> None:
        """LiveState must reject infinite or NaN SoC values."""
        from math import inf
        with pytest.raises(ValueError, match="finite"):
            LiveState(**self._make_base(soc_pct=inf))

    def test_rejects_nonfinite_pv_power(self) -> None:
        """LiveState must reject infinite or NaN PV power values."""
        from math import nan
        with pytest.raises(ValueError, match="finite"):
            LiveState(**self._make_base(pv_power_w=nan))

    def test_rejects_negative_grid_export(self) -> None:
        """grid_export_w must be non-negative — negative means import."""
        with pytest.raises(ValueError, match="grid_export_w"):
            LiveState(**self._make_base(grid_export_w=-100.0))

    def test_rejects_negative_battery_charge(self) -> None:
        """battery_charge_w must be non-negative."""
        with pytest.raises(ValueError, match="battery_charge_w"):
            LiveState(**self._make_base(battery_charge_w=-50.0))

    def test_accepts_zero_grid_export(self) -> None:
        """Zero grid export is valid (boundary)."""
        live = LiveState(**self._make_base(grid_export_w=0.0))
        assert live.grid_export_w == 0.0

    def test_accepts_zero_battery_charge(self) -> None:
        """Zero battery charge is valid (boundary)."""
        live = LiveState(**self._make_base(battery_charge_w=0.0))
        assert live.battery_charge_w == 0.0

    def test_accepts_positive_values(self) -> None:
        """All positive values are valid."""
        live = LiveState(**self._make_base())
        assert live.grid_export_w == 2000.0
        assert live.battery_charge_w == 0.0


class TestForecastPointValidation:
    """Tests for ForecastPoint input validation."""

    def test_rejects_infinite_power(self) -> None:
        """Forecast power must not be infinite."""
        from math import inf
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="finite"):
            ForecastPoint(start=now, duration=timedelta(minutes=15), power_w=inf)

    def test_rejects_nan_power(self) -> None:
        """Forecast power must not be NaN."""
        from math import nan
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="finite"):
            ForecastPoint(start=now, duration=timedelta(minutes=15), power_w=nan)

    def test_rejects_negative_power(self) -> None:
        """Forecast power must be non-negative."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="non-negative"):
            ForecastPoint(start=now, duration=timedelta(minutes=15), power_w=-100.0)

    def test_accepts_zero_power(self) -> None:
        """Zero forecast power is valid (nighttime)."""
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        fp = ForecastPoint(start=now, duration=timedelta(minutes=15), power_w=0.0)
        assert fp.power_w == 0.0


class TestStorageCapabilitiesValidation:
    """Tests for StorageCapabilities input validation."""

    def test_rejects_zero_usable_capacity(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            StorageCapabilities(usable_capacity_kwh=0.0, max_charge_power_w=5000.0)

    def test_rejects_zero_max_charge_power(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            StorageCapabilities(usable_capacity_kwh=10.0, max_charge_power_w=0.0)

    def test_rejects_negative_values(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            StorageCapabilities(usable_capacity_kwh=-1.0, max_charge_power_w=5000.0)

    def test_accepts_positive_values(self) -> None:
        cap = StorageCapabilities(usable_capacity_kwh=10.0, max_charge_power_w=5000.0)
        assert cap.usable_capacity_kwh == 10.0
        assert cap.max_charge_power_w == 5000.0


class TestPlannerConfigValidation:
    """Tests for PlannerConfig input validation."""

    def test_rejects_target_below_zero(self) -> None:
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="between 0 and 100"):
            PlannerConfig(target_soc_pct=-1.0, charge_end=now + timedelta(hours=4))

    def test_rejects_target_above_100(self) -> None:
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="between 0 and 100"):
            PlannerConfig(target_soc_pct=101.0, charge_end=now + timedelta(hours=4))

    def test_accepts_boundary_targets(self) -> None:
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        PlannerConfig(target_soc_pct=0.0, charge_end=now + timedelta(hours=4))
        PlannerConfig(target_soc_pct=100.0, charge_end=now + timedelta(hours=4))

    def test_rejects_unfinite_target(self) -> None:
        now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        from math import inf
        with pytest.raises(ValueError, match="finite"):
            PlannerConfig(target_soc_pct=inf, charge_end=now + timedelta(hours=4))
