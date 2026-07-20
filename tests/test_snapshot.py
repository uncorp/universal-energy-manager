from datetime import UTC, datetime, timedelta

import pytest

from custom_components.universal_energy_manager.snapshot import (
    StateSample,
    build_live_state,
)


def test_build_live_state_normalizes_e3dc_power_measurements() -> None:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3.2", "kW", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("2.4", "kW", now),
        battery_charge=StateSample("0", "W", now),
    )

    assert live.soc_pct == 55.0
    assert live.pv_power_w == 3200.0
    assert live.house_power_w == 800.0
    assert live.grid_export_w == 2400.0


def test_build_live_state_uses_oldest_timestamp() -> None:
    """The live-state timestamp must be the minimum across all samples."""
    base = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    soc = StateSample("50", "%", base)
    pv = StateSample("2000", "W", base)
    house = StateSample("500", "W", base)
    grid = StateSample("1500", "W", base)
    batt = StateSample("0", "W", base - timedelta(minutes=5))

    live = build_live_state(
        now=base,
        soc=soc,
        pv_power=pv,
        house_power=house,
        grid_export=grid,
        battery_charge=batt,
    )
    assert live.timestamp == base - timedelta(minutes=5)


def test_build_live_state_rejects_invalid_soc_unit() -> None:
    """SoC with an unknown unit must raise ValueError, never silently guess."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    soc_bad = StateSample("50", "kWh", now)

    with pytest.raises(ValueError, match="unsupported state-of-charge unit"):
        build_live_state(
            now=now,
            soc=soc_bad,
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )

    with pytest.raises(ValueError, match="unsupported state-of-charge unit"):
        build_live_state(
            now=now,
            soc=StateSample("50", "percent", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_non_numeric_soc() -> None:
    """Non-numeric SoC values must raise ValueError."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="state of charge is not numeric"):
        build_live_state(
            now=now,
            soc=StateSample("unavailable", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_negative_soc() -> None:
    """Negative SoC must be rejected by LiveState validation."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="soc_pct"):
        build_live_state(
            now=now,
            soc=StateSample("-5", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_soc_above_100() -> None:
    """SoC above 100 % must be rejected."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="soc_pct"):
        build_live_state(
            now=now,
            soc=StateSample("105", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_negative_power() -> None:
    """Negative PV / house power values must be rejected."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="pv_power"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("-100", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )

    with pytest.raises(ValueError, match="house_power"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("-100", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_unknown_power_unit() -> None:
    """Unknown power units (e.g. MW) must raise ValueError."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="unsupported power unit"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2", "MW", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_handles_kw_decimal_precision() -> None:
    """kW values with many decimal places should be normalized accurately."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("50", "%", now),
        pv_power=StateSample("1.23456", "kW", now),
        house_power=StateSample("0.789", "kW", now),
        grid_export=StateSample("0.44556", "kW", now),
        battery_charge=StateSample("0", "W", now),
    )
    assert live.pv_power_w == pytest.approx(1234.56)
    assert live.house_power_w == pytest.approx(789.0)
    assert live.grid_export_w == pytest.approx(445.56)


def test_build_live_state_accepts_none_unit_as_watts() -> None:
    """A None unit on power values must be treated as watts."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("50", None, now),
        pv_power=StateSample("3000", None, now),
        house_power=StateSample("500", None, now),
        grid_export=StateSample("2500", None, now),
        battery_charge=StateSample("0", None, now),
    )
    assert live.pv_power_w == 3000.0
    assert live.house_power_w == 500.0
    assert live.grid_export_w == 2500.0


def test_build_live_state_rejects_negative_grid_export() -> None:
    """Negative grid_export must be rejected — that indicates import."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="grid_export"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("-100", "W", now),
            battery_charge=StateSample("0", "W", now),
        )


def test_build_live_state_rejects_negative_battery_charge() -> None:
    """Negative battery charge must be rejected."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="battery_charge"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("-50", "W", now),
        )


def test_build_live_state_rejects_non_numeric_battery_charge() -> None:
    """Non-numeric battery charge must propagate a ValueError."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="not numeric"):
        build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("unavailable", "W", now),
        )


def test_build_live_state_validates_soc_pct_in_live_state() -> None:
    """SoC validation must also be caught by LiveState __post_init__."""
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="soc_pct"):
        build_live_state(
            now=now,
            soc=StateSample("150", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
