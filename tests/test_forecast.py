from datetime import UTC, datetime, timedelta

from custom_components.universal_energy_manager.forecast import combine_producer_forecasts
from custom_components.universal_energy_manager.models import ForecastPoint


def test_combine_producer_forecasts_sums_each_aligned_interval() -> None:
    start = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    combined = combine_producer_forecasts(
        (
            (
                ForecastPoint(start, timedelta(minutes=15), 1000.0),
                ForecastPoint(start + timedelta(minutes=15), timedelta(minutes=15), 800.0),
            ),
            (
                ForecastPoint(start, timedelta(minutes=15), 400.0),
                ForecastPoint(start + timedelta(minutes=15), timedelta(minutes=15), 200.0),
            ),
        )
    )

    assert [point.power_w for point in combined] == [1400.0, 1000.0]
