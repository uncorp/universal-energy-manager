"""Tests for forecast_from_hourly_energy and forecast_from_minute_data.

These functions are used by the coordinator to convert raw entity attributes
into ForecastPoint sequences. They are exercised indirectly through the
coordinator, but direct unit tests ensure error paths are covered."""
from datetime import timedelta

import pytest

from custom_components.universal_energy_manager.forecast import (
    forecast_from_hourly_energy,
    forecast_from_minute_data,
)


class TestForecastFromHourlyEnergy:
    """Tests for forecast_from_hourly_energy."""

    def test_parses_valid_hourly_energy(self) -> None:
        """Valid hourly energy dict must produce sorted ForecastPoints."""
        data = {
            "2026-07-18T10:00:00+02:00": 1500.0,
            "2026-07-18T11:00:00+02:00": 2000.0,
        }
        points = forecast_from_hourly_energy(data)
        assert len(points) == 2
        assert points[0].power_w == 1500.0
        assert points[1].power_w == 2000.0
        assert all(p.duration == timedelta(hours=1) for p in points)
        assert points[0].start < points[1].start

    def test_rejects_non_timezone_aware_timestamps(self) -> None:
        """Timestamps without timezone info must raise ValueError."""
        data = {"2026-07-18T10:00:00": 1500.0}
        with pytest.raises(ValueError, match="timezone-aware"):
            forecast_from_hourly_energy(data)

    def test_rejects_negative_energy(self) -> None:
        """Negative energy values must raise ValueError."""
        data = {"2026-07-18T10:00:00+02:00": -100.0}
        with pytest.raises(ValueError, match="non-negative"):
            forecast_from_hourly_energy(data)

    def test_rejects_invalid_timestamps(self) -> None:
        """Non-parseable timestamps must raise ValueError."""
        data = {"not-a-timestamp": 1500.0}
        with pytest.raises(ValueError, match="invalid forecast timestamp"):
            forecast_from_hourly_energy(data)

    def test_empty_dict_returns_empty_tuple(self) -> None:
        """An empty dict must return an empty tuple."""
        assert forecast_from_hourly_energy({}) == ()

    def test_int_energy_values_are_accepted(self) -> None:
        """Integer energy values must be converted to float power."""
        data = {"2026-07-18T10:00:00+02:00": 1500}  # type: ignore[dict-item]
        points = forecast_from_hourly_energy(data)
        assert points[0].power_w == 1500.0


class TestForecastFromMinuteData:
    """Tests for forecast_from_minute_data."""

    def test_parses_valid_minute_data(self) -> None:
        """Valid minute-data dict must produce 15-minute ForecastPoints."""
        data = {
            "2026-07-18T10:00:00+02:00": 375.0,
            "2026-07-18T10:15:00+02:00": 500.0,
        }
        points = forecast_from_minute_data(data)
        assert len(points) == 2
        # 375 Wh over 15 min => 375*4 = 1500 W
        assert points[0].power_w == 1500.0
        # 500 Wh over 15 min => 500*4 = 2000 W
        assert points[1].power_w == 2000.0
        assert all(p.duration == timedelta(minutes=15) for p in points)

    def test_rejects_non_timezone_aware_timestamps(self) -> None:
        """Timestamps without timezone info must raise ValueError."""
        data = {"2026-07-18T10:00:00": 375.0}
        with pytest.raises(ValueError, match="timezone-aware"):
            forecast_from_minute_data(data)

    def test_rejects_negative_energy(self) -> None:
        """Negative energy values must raise ValueError."""
        data = {"2026-07-18T10:00:00+02:00": -100.0}
        with pytest.raises(ValueError, match="non-negative"):
            forecast_from_minute_data(data)

    def test_empty_dict_returns_empty_tuple(self) -> None:
        """An empty dict must return an empty tuple."""
        assert forecast_from_minute_data({}) == ()

    def test_unsorted_keys_are_sorted(self) -> None:
        """Input dict with unsorted keys must return sorted points."""
        data = {
            "2026-07-18T10:30:00+02:00": 375.0,
            "2026-07-18T10:00:00+02:00": 500.0,
        }
        points = forecast_from_minute_data(data)
        assert points[0].start < points[1].start

    def test_rejects_invalid_timestamps(self) -> None:
        """Non-parseable timestamps must raise ValueError."""
        data = {"not-a-timestamp": 375.0}
        with pytest.raises(ValueError, match="invalid forecast timestamp"):
            forecast_from_minute_data(data)
