from datetime import UTC, datetime

import pytest

from custom_components.universal_energy_manager.forecast_solar import (
    async_read_forecast_solar,
    forecast_points_from_wh_hours,
)


def test_forecast_solar_hourly_energy_becomes_power_forecast_point() -> None:
    points = forecast_points_from_wh_hours(
        {"2026-07-18T10:00:00+00:00": 1250.0}
    )

    assert len(points) == 1
    assert points[0].start == datetime(2026, 7, 18, 10, tzinfo=UTC)
    assert points[0].power_w == 1250.0
    assert points[0].duration.total_seconds() == 3600


def test_forecast_solar_rejects_naive_or_negative_energy() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        forecast_points_from_wh_hours({"2026-07-18T10:00:00": 1.0})
    with pytest.raises(ValueError, match="non-negative"):
        forecast_points_from_wh_hours({"2026-07-18T10:00:00+00:00": -1.0})


@pytest.mark.asyncio
async def test_async_reader_combines_cached_curves_from_multiple_arrays() -> None:
    async def fetch(_hass: object, entry_id: str):
        return {
            "wh_hours": {
                "2026-07-18T10:00:00+00:00": 1000.0 if entry_id == "roof" else 250.0
            }
        }

    points = await async_read_forecast_solar(
        object(),
        ("roof", "balcony"),
        fetch=fetch,
    )

    assert len(points) == 1
    assert points[0].power_w == 1250.0
