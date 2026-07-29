"""Regression tests: signed values for battery_charge and grid_export (Req 1-3).

Requirement 1: Batterie gibt es nur als EINZELE Entität "Batterieleistung" —
              ein einziger Sensor mit signed Werten (laden = positiv, entladen = negativ
              oder umgekehrt).
Requirement 2: Netzleistung ist EINZELE Entität mit signed Werten —
              Import/Export über eine einzige Zahl abbilden.
Requirement 3: Hausverbrauch darf negative Werte haben (Balkonkraftwerk).

Diese Tests prüfen, dass build_live_state negative Werte für
house_power, grid_export und battery_charge akzeptiert — weil diese Felder
signed Werte repräsentieren, nicht nur positive Messwerte.

Der vorherige Stand (vor v0.1.8-rc.1) hat negative Werte abgelehnt, was
gegen die neuen UX-Anforderungen verstößt.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.universal_energy_manager.models import LiveState
from custom_components.universal_energy_manager.snapshot import (
    StateSample,
    build_live_state,
)


def _now() -> datetime:
    return datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


# =========================================================================== #
# TEST 1: build_live_state accepts negative house_power (Req 3)              #
# =========================================================================== #


class TestSignedHousePower:
    """Req 3: Negative house_power means balcony PV produces more than the house
    consumes — this is a valid signed value for the house_power field."""

    def test_build_live_state_accepts_negative_house_power(self) -> None:
        """build_live_state must accept a negative house_power value."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("-250", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
        assert live.house_power_w == -250.0

    def test_build_live_state_accepts_zero_house_power(self) -> None:
        """Zero house_power must also work."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("0", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
        assert live.house_power_w == 0.0

    def test_build_live_state_accepts_positive_house_power(self) -> None:
        """Positive house_power must still work."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
        assert live.house_power_w == 800.0


# =========================================================================== #
# TEST 2: build_live_state accepts negative grid_export (Req 2)              #
# =========================================================================== #


class TestSignedGridExport:
    """Req 2: grid_export is a signed entity. Negative = import, positive = export.
    The single "Netzleistung" entity represents both import and export."""

    def test_build_live_state_accepts_negative_grid_export(self) -> None:
        """build_live_state must accept a negative grid_export value (import)."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("-100", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
        assert live.grid_export_w == -100.0

    def test_build_live_state_accepts_positive_grid_export(self) -> None:
        """Positive grid_export (export) must still work."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("0", "W", now),
        )
        assert live.grid_export_w == 1500.0


# =========================================================================== #
# TEST 3: build_live_state accepts negative battery_charge (Req 1)           #
# =========================================================================== #


class TestSignedBatteryCharge:
    """Req 1: battery_charge is a signed entity. Positive = charging, negative
    = discharging (or vice versa). The single "Batterieleistung" entity
    represents both directions."""

    def test_build_live_state_accepts_negative_battery_charge(self) -> None:
        """build_live_state must accept a negative battery_charge value (discharging)."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("-50", "W", now),
        )
        assert live.battery_charge_w == -50.0

    def test_build_live_state_accepts_positive_battery_charge(self) -> None:
        """Positive battery_charge (charging) must still work."""
        now = _now()
        live = build_live_state(
            now=now,
            soc=StateSample("50", "%", now),
            pv_power=StateSample("2000", "W", now),
            house_power=StateSample("500", "W", now),
            grid_export=StateSample("1500", "W", now),
            battery_charge=StateSample("3000", "W", now),
        )
        assert live.battery_charge_w == 3000.0


# =========================================================================== #
# TEST 4: LiveState __post_init__ accepts signed values                       #
# =========================================================================== #


class TestLiveStateSignedValues:
    """LiveState.__post_init__ must not reject negative values for
    house_power_w, grid_export_w, or battery_charge_w — these are signed fields."""

    def test_live_state_accepts_negative_house_power(self) -> None:
        now = _now()
        ls = LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=2000.0,
            house_power_w=-250.0,
            grid_export_w=1500.0,
            battery_charge_w=0.0,
        )
        assert ls.house_power_w == -250.0

    def test_live_state_accepts_negative_grid_export(self) -> None:
        now = _now()
        ls = LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=2000.0,
            house_power_w=500.0,
            grid_export_w=-100.0,
            battery_charge_w=0.0,
        )
        assert ls.grid_export_w == -100.0

    def test_live_state_accepts_negative_battery_charge(self) -> None:
        now = _now()
        ls = LiveState(
            timestamp=now,
            now=now,
            soc_pct=50.0,
            pv_power_w=2000.0,
            house_power_w=500.0,
            grid_export_w=1500.0,
            battery_charge_w=-50.0,
        )
        assert ls.battery_charge_w == -50.0


# =========================================================================== #
# TEST 5: PV power and SoC are STILL required to be non-negative              #
# =========================================================================== #


class TestPositiveConstraintsStillApply:
    """PV power and SoC must remain non-negative — only house/grid/battery
    are signed."""

    def test_pv_power_still_rejects_negative(self) -> None:
        now = _now()
        with pytest.raises(ValueError, match="pv_power"):
            LiveState(
                timestamp=now,
                now=now,
                soc_pct=50.0,
                pv_power_w=-100.0,
                house_power_w=500.0,
                grid_export_w=1500.0,
                battery_charge_w=0.0,
            )

    def test_soc_still_rejects_negative(self) -> None:
        now = _now()
        with pytest.raises(ValueError, match="soc_pct"):
            LiveState(
                timestamp=now,
                now=now,
                soc_pct=-5.0,
                pv_power_w=2000.0,
                house_power_w=500.0,
                grid_export_w=1500.0,
                battery_charge_w=0.0,
            )
