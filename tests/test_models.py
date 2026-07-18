from datetime import UTC, datetime

import pytest

from custom_components.universal_energy_manager.models import LiveState


def test_live_state_rejects_stale_measurements() -> None:
    with pytest.raises(ValueError, match="stale"):
        LiveState(
            timestamp=datetime(2026, 7, 18, 8, 0, tzinfo=UTC),
            now=datetime(2026, 7, 18, 8, 16, tzinfo=UTC),
            soc_pct=55.0,
            pv_power_w=3000.0,
            house_power_w=800.0,
            grid_export_w=500.0,
            battery_charge_w=1200.0,
        )
