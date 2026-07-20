from datetime import UTC, datetime, timedelta

from custom_components.universal_energy_manager.forecast import combine_producer_forecasts
from custom_components.universal_energy_manager.models import ForecastPoint


def test_combine_producer_forecasts_returns_empty_tuple_for_empty_input() -> None:
    """An empty input must return an empty tuple, not crash."""
    combined = combine_producer_forecasts(())
    assert combined == ()


def test_combine_producer_forecasts_returns_empty_tuple_for_empty_list() -> None:
    """An input list containing only empty tuples must return an empty tuple."""
    combined = combine_producer_forecasts(((), ()))
    assert combined == ()


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

    # Must be sorted by start time
    assert combined[0].start < combined[1].start


def test_combine_producer_forecasts_handles_unaligned_intervals() -> None:
    """Different time intervals must not be merged."""
    start = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    combined = combine_producer_forecasts(
        (
            (
                ForecastPoint(start, timedelta(minutes=15), 1000.0),
            ),
            (
                ForecastPoint(start + timedelta(minutes=15), timedelta(minutes=15), 500.0),
            ),
        )
    )

    assert len(combined) == 2
    assert [point.power_w for point in combined] == [1000.0, 500.0]
