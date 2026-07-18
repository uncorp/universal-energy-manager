from datetime import UTC, datetime

from custom_components.universal_energy_manager.snapshot import StateSample, build_live_state


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
