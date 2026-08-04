"""TDD tests for UEM Task B: Multi-Quelle/MMulti-Akku -- Generator power aggregation.

Slice 4: The coordinator sums generator power entities into the live-state
PV power.  The E3DC-PV entity (CONF_PV_POWER_ENTITY) is always included;
additional generators from CONF_GENERATORS add their power_entity values.

The sum is zero when no generators are configured, and uses the same unit
normalisation (W/kW) as the E3DC entities.  Invalid/unavailable generator
entities are skipped without crashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


@dataclass
class FakeState:
    """Minimal mock of a Home Assistant state object."""
    state: str
    last_updated: datetime
    attributes: dict = None

    def __post_init__(self) -> None:
        if self.attributes is None:
            self.attributes: dict = {}


def _tznow() -> datetime:
    return datetime.now(UTC)


def _make_entry(hass: MagicMock, data: dict) -> MagicMock:
    """Return a ConfigEntry-like object with the given data."""
    entry = MagicMock()
    entry.data = data
    entry.entry_id = "uem-test"
    return entry


def _make_coordinator(
    hass: MagicMock,
    entry_data: dict,
    entity_states: dict[str, FakeState],
) -> UemShadowCoordinator:
    """Build a coordinator whose hass.states.get returns the given states."""
    entry = _make_entry(hass, entry_data)
    coord = UemShadowCoordinator(hass, entry)
    # Patch hass.states.get to return our fake states
    coord.hass = hass
    hass.states.get = MagicMock(
        side_effect=lambda eid: entity_states.get(eid)
        if eid in entity_states
        else None,
    )
    return coord


def _base_entry_data() -> dict:
    return {
        "soc_entity": "sensor.e3dc_soc",
        "pv_power_entity": "sensor.e3dc_pv",
        "house_power_entity": "sensor.e3dc_house",
        "grid_export_entity": "sensor.e3dc_grid",
        "battery_charge_entity": "sensor.e3dc_charge",
        "battery_capacity_entity": "sensor.e3dc_capacity",
        "max_charge_power_entity": "sensor.e3dc_max",
    }


def _base_states() -> dict[str, FakeState]:
    now = _tznow()
    return {
        "sensor.e3dc_soc": FakeState("50", now, {"unit_of_measurement": "%"}),
        "sensor.e3dc_pv": FakeState("3000", now, {"unit_of_measurement": "W"}),
        "sensor.e3dc_house": FakeState("1500", now, {"unit_of_measurement": "W"}),
        "sensor.e3dc_grid": FakeState("-500", now, {"unit_of_measurement": "W"}),
        "sensor.e3dc_charge": FakeState("0", now, {"unit_of_measurement": "W"}),
        "sensor.e3dc_capacity": FakeState("20", now, {"unit_of_measurement": "kWh"}),
        "sensor.e3dc_max": FakeState("5000", now, {"unit_of_measurement": "W"}),
    }


# =========================================================================== #
# TEST 1: Zero generators -- PV power unchanged (baseline)                    #
# =========================================================================== #


def test_no_generators_pv_unchanged():
    """Without any configured generators, live pv_power_w equals the E3DC entity."""
    hass = MagicMock()
    entry_data = _base_entry_data()
    states = _base_states()

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    assert live.pv_power_w == pytest.approx(3000.0)


# =========================================================================== #
# TEST 2: One additional generator -- PV power = E3DC + generator             #
# =========================================================================== #


def test_one_generator_adds_to_pv_power():
    """A single additional generator's power_entity is summed into pv_power_w."""
    hass = MagicMock()
    now = _tznow()
    entry_data = _base_entry_data()
    gen_json = (
        '[{"generator_name": "Balkon", '
        '"generator_power_entity": "sensor.balkon_pv"}]'
    )
    entry_data["generators"] = gen_json

    states = _base_states()
    states["sensor.balkon_pv"] = FakeState("600", now, {"unit_of_measurement": "W"})

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    # E3DC 3000 W + Balkon 600 W = 3600 W
    assert live.pv_power_w == pytest.approx(3600.0)


# =========================================================================== #
# TEST 3: Multiple generators -- all summed                                   #
# =========================================================================== #


def test_multiple_generators_all_summed():
    """Two additional generators are both included in the PV sum."""
    hass = MagicMock()
    now = _tznow()
    entry_data = _base_entry_data()
    gen_json = (
        '[{"generator_name": "Balkon", '
        '"generator_power_entity": "sensor.balkon_pv"}, '
        '{"generator_name": "Garage", '
        '"generator_power_entity": "sensor.garage_pv"}]'
    )
    entry_data["generators"] = gen_json

    states = _base_states()
    states["sensor.balkon_pv"] = FakeState("400", now, {"unit_of_measurement": "W"})
    states["sensor.garage_pv"] = FakeState("200", now, {"unit_of_measurement": "W"})

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    # E3DC 3000 + Balkon 400 + Garage 200 = 3600 W
    assert live.pv_power_w == pytest.approx(3600.0)


# =========================================================================== #
# TEST 4: Generator in kW is converted correctly                              #
# =========================================================================== #


def test_generator_kw_unit_converted():
    """A generator reporting in kW is normalised to W before summing."""
    hass = MagicMock()
    now = _tznow()
    entry_data = _base_entry_data()
    gen_json = (
        '[{"generator_name": "BHKW", '
        '"generator_power_entity": "sensor.bhkw_power"}]'
    )
    entry_data["generators"] = gen_json

    states = _base_states()
    states["sensor.bhkw_power"] = FakeState(
        "1.5", now, {"unit_of_measurement": "kW"},
    )

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    # E3DC 3000 + BHKW 1500 W = 4500 W
    assert live.pv_power_w == pytest.approx(4500.0)


# =========================================================================== #
# TEST 5: Unavailable generator is skipped                                    #
# =========================================================================== #


def test_unavailable_generator_skipped():
    """An unavailable generator entity is silently skipped."""
    hass = MagicMock()
    now = _tznow()
    entry_data = _base_entry_data()
    gen_json = (
        '[{"generator_name": "Balkon", '
        '"generator_power_entity": "sensor.balkon_pv"}, '
        '{"generator_name": "Garage", '
        '"generator_power_entity": "sensor.garage_pv"}]'
    )
    entry_data["generators"] = gen_json

    states = _base_states()
    states["sensor.balkon_pv"] = FakeState("400", now, {"unit_of_measurement": "W"})
    states["sensor.garage_pv"] = FakeState(
        "unavailable", now, {"unit_of_measurement": "W"},
    )

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    # E3DC 3000 + Balkon 400 (Garage skipped) = 3400 W
    assert live.pv_power_w == pytest.approx(3400.0)


# =========================================================================== #
# TEST 6: Malformed generator JSON is handled gracefully                      #
# =========================================================================== #


def test_malformed_generators_json_handled():
    """Malformed generator JSON → treated as no generators."""
    hass = MagicMock()
    entry_data = _base_entry_data()
    entry_data["generators"] = "{invalid json here"

    states = _base_states()

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    assert live.pv_power_w == pytest.approx(3000.0)


# =========================================================================== #
# TEST 7: Generator entity missing from HA entirely                           #
# =========================================================================== #


def test_generator_entity_missing_from_ha():
    """A generator entity not present in HA is skipped."""
    hass = MagicMock()
    entry_data = _base_entry_data()
    gen_json = (
        '[{"generator_name": "Balkon", '
        '"generator_power_entity": "sensor.nonexistent"}]'
    )
    entry_data["generators"] = gen_json

    states = _base_states()
    # sensor.nonexistent is not in states

    coord = _make_coordinator(hass, entry_data, states)
    live = coord._live_state()
    # Only E3DC PV counts
    assert live.pv_power_w == pytest.approx(3000.0)
