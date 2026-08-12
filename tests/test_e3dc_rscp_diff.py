"""Regression tests for the open diff in e3dc_rscp.py."""

from __future__ import annotations

import importlib.util
import sys

# --- bootstrap: load e3dc_rscp as a standalone module without __init__.py ---
# Use package import path so it works both locally and in CI (pytest pythonpath=.)
spec = importlib.util.spec_from_file_location(
    "custom_components.universal_energy_manager.e3dc_rscp",
    "custom_components/universal_energy_manager/e3dc_rscp.py",
)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
mod.__path__ = []
sys.modules["custom_components.universal_energy_manager.e3dc_rscp"] = mod
spec.loader.exec_module(mod)

source_key_from_unique_id = mod.source_key_from_unique_id
discover_e3dc_entities = mod.discover_e3dc_entities
source_by_key_from_unique_ids = mod.source_by_key_from_unique_ids
_ACTUAL_SUFFIX_MAP = mod._ACTUAL_SUFFIX_MAP
_LEGACY_KEYS = mod._LEGACY_KEYS
_SOURCE_KEYS = mod._SOURCE_KEYS


# ======================================================================
# source_key_from_unique_id
# ======================================================================


def test_source_key_from_unique_id_only_accepts_known_e3dc_rscp_suffixes() -> None:
    """Existing test — must still pass."""
    assert source_key_from_unique_id("abc123_soc") == "soc"
    assert source_key_from_unique_id("abc123_solar-production") == "solar-production"
    assert source_key_from_unique_id("abc123_other") is None


def test_actual_suffix_map_all_resolved() -> None:
    """Every key in _ACTUAL_SUFFIX_MAP is discoverable by source_key_from_unique_id."""
    for suffix, expected_key in _ACTUAL_SUFFIX_MAP.items():
        result = source_key_from_unique_id(f"abc123_{suffix}")
        assert result == expected_key, f"suffix {suffix!r} -> expected {expected_key}, got {result}"


def test_current_operation_mode_not_colliding_with_mode() -> None:
    """Regression: 'current_operation_mode' must not be misidentified as 'mode'.

    The original bug was that _ACTUAL_SUFFIX_MAP iteration placed 'mode'
    (index 16) before 'current_operation_mode' (index 17). Since
    current_operation_mode ends with 'mode', the endswith("mode") check
    at index 16 matched first, returning 'mode' instead of the correct
    'current_operation_mode'.

    Fix: iterate in reverse so longer suffixes are checked first.
    """
    assert source_key_from_unique_id("abc123_mode") == "mode"
    assert source_key_from_unique_id("abc123_current_operation_mode") == "current_operation_mode"
    assert source_key_from_unique_id("serial_current_operation_mode") == "current_operation_mode"


def test_legacy_keys_still_work() -> None:
    """Legacy keys remain in _LEGACY_KEYS and are resolved."""
    for key in _LEGACY_KEYS:
        result = source_key_from_unique_id(f"abc123_{key}")
        assert result == key, f"Legacy key {key!r} not found"


# ======================================================================
# discover_e3dc_entities — legacy keys (backward compat)
# ======================================================================


def test_discovery_prefills_known_e3dc_rscp_measurements_legacy() -> None:
    """Existing test — backward compatibility with legacy key names."""
    discovered = discover_e3dc_entities(
        {
            "soc": "sensor.e3dc_state_of_charge",
            "solar-production": "sensor.e3dc_solar_production",
            "house-consumption": "sensor.e3dc_house_consumption",
            "grid-netchange": "sensor.e3dc_grid_netchange",
            "battery-charge": "sensor.e3dc_battery_charge",
            "system-battery-installed-capacity": "sensor.e3dc_battery_capacity",
            "system-battery-charge-max": "sensor.e3dc_max_charge_power",
        }
    )

    assert discovered.soc == "sensor.e3dc_state_of_charge"
    assert discovered.pv_power == "sensor.e3dc_solar_production"
    assert discovered.house_power == "sensor.e3dc_house_consumption"
    assert discovered.grid_export == "sensor.e3dc_grid_netchange"
    assert discovered.battery_charge == "sensor.e3dc_battery_charge"
    assert discovered.battery_capacity == "sensor.e3dc_battery_capacity"
    assert discovered.max_charge_power == "sensor.e3dc_max_charge_power"


def test_discovery_prefills_known_e3dc_rscp_measurements_actual() -> None:
    """New S10E Pro / actual naming paths are correctly resolved."""
    discovered = discover_e3dc_entities(
        {
            "soc": "sensor.e3dc_soc",
            "pv_power": "sensor.e3dc_pv",
            "house_power": "sensor.e3dc_house",
            "consumption_from_grid": "sensor.e3dc_grid_import",
            "export_to_grid": "sensor.e3dc_grid_export",
            "battery_charge": "sensor.e3dc_batt_charge",
            "installed_battery_capacity": "sensor.e3dc_batt_cap",
            "system_maximum_charge": "sensor.e3dc_max_charge",
            "battery_discharge": "sensor.e3dc_batt_discharge",
            "derate_feed_above": "sensor.e3dc_derate",
            "autarky": "sensor.e3dc_autarky",
            "self_consumption": "sensor.e3dc_self_consumption",
            "energy_charged_from_grid": "sensor.e3dc_energy_charged",
            "mode": "sensor.e3dc_mode",
            "current_operation_mode": "sensor.e3dc_op_mode",
            "current_power_value": "sensor.e3dc_cur_power",
            "sg_ready": "sensor.e3dc_sg_ready",
            "additional_total": "sensor.e3dc_add_total",
            "additional": "sensor.e3dc_additional",
            "additional_consumption_total": "sensor.e3dc_add_consumption_total",
            "additional_consumption": "sensor.e3dc_add_consumption",
            "wallbox_consumption": "sensor.e3dc_wallbox",
            "installed_peak_power": "sensor.e3dc_peak_power",
            "battery_charge_today": "sensor.e3dc_batt_charge_today",
            "battery_discharge_today": "sensor.e3dc_batt_discharge_today",
            "consumption_from_grid_today": "sensor.e3dc_grid_import_today",
            "export_to_grid_today": "sensor.e3dc_grid_export_today",
            "house_consumption_today": "sensor.e3dc_house_consumption_today",
            "solar_production_today": "sensor.e3dc_solar_production_today",
            "autarky_today": "sensor.e3dc_autarky_today",
            "self_consumption_today": "sensor.e3dc_self_consumption_today",
        }
    )

    assert discovered.soc == "sensor.e3dc_soc"
    assert discovered.pv_power == "sensor.e3dc_pv"
    assert discovered.house_power == "sensor.e3dc_house"
    # grid_export chain: grid-netchange > export_to_grid > consumption_from_grid > grid_export
    # export_to_grid (line 160) comes before consumption_from_grid (line 161)
    assert discovered.grid_export == "sensor.e3dc_grid_export"
    assert discovered.battery_charge == "sensor.e3dc_batt_charge"
    assert discovered.battery_capacity == "sensor.e3dc_batt_cap"
    assert discovered.max_charge_power == "sensor.e3dc_max_charge"
    assert discovered.battery_discharge == "sensor.e3dc_batt_discharge"
    assert discovered.derate_feed_above == "sensor.e3dc_derate"
    assert discovered.autarky == "sensor.e3dc_autarky"
    assert discovered.self_consumption == "sensor.e3dc_self_consumption"
    assert discovered.energy_charged_from_grid == "sensor.e3dc_energy_charged"
    assert discovered.mode == "sensor.e3dc_mode"
    assert discovered.current_operation_mode == "sensor.e3dc_op_mode"
    assert discovered.current_power_value == "sensor.e3dc_cur_power"
    assert discovered.sg_ready == "sensor.e3dc_sg_ready"
    assert discovered.additional_total == "sensor.e3dc_add_total"
    assert discovered.additional == "sensor.e3dc_additional"
    assert discovered.additional_consumption_total == "sensor.e3dc_add_consumption_total"
    assert discovered.additional_consumption == "sensor.e3dc_add_consumption"
    assert discovered.wallbox_consumption == "sensor.e3dc_wallbox"
    assert discovered.installed_peak_power == "sensor.e3dc_peak_power"
    assert discovered.battery_charge_today == "sensor.e3dc_batt_charge_today"
    assert discovered.battery_discharge_today == "sensor.e3dc_batt_discharge_today"
    assert discovered.consumption_from_grid_today == "sensor.e3dc_grid_import_today"
    assert discovered.export_to_grid_today == "sensor.e3dc_grid_export_today"
    assert discovered.house_consumption_today == "sensor.e3dc_house_consumption_today"
    assert discovered.solar_production_today == "sensor.e3dc_solar_production_today"
    assert discovered.autarky_today == "sensor.e3dc_autarky_today"
    assert discovered.self_consumption_today == "sensor.e3dc_self_consumption_today"


def test_discovery_empty_dict() -> None:
    """All fields should be None when no source keys provided."""
    discovered = discover_e3dc_entities({})
    for attr in [
        "soc",
        "pv_power",
        "house_power",
        "grid_export",
        "battery_charge",
        "battery_capacity",
        "max_charge_power",
        "battery_discharge",
        "derate_feed_above",
        "autarky",
        "self_consumption",
        "energy_charged_from_grid",
        "mode",
        "current_operation_mode",
        "current_power_value",
        "sg_ready",
        "additional_total",
        "additional",
        "additional_consumption_total",
        "additional_consumption",
        "wallbox_consumption",
        "installed_peak_power",
        "battery_charge_today",
        "battery_discharge_today",
        "consumption_from_grid_today",
        "export_to_grid_today",
        "house_consumption_today",
        "solar_production_today",
        "autarky_today",
        "self_consumption_today",
    ]:
        assert getattr(discovered, attr) is None, f"{attr} should be None"


# ======================================================================
# discover_e3dc_entities — fallback chains
# ======================================================================


def test_grid_export_fallback_chain() -> None:
    """grid_export tries: grid-netchange > export_to_grid > consumption_from_grid > grid_export."""
    assert discover_e3dc_entities({"grid-netchange": "g1"}).grid_export == "g1"
    assert discover_e3dc_entities({"export_to_grid": "g2"}).grid_export == "g2"
    assert discover_e3dc_entities({"consumption_from_grid": "g3"}).grid_export == "g3"
    assert discover_e3dc_entities({"grid_export": "g4"}).grid_export == "g4"
    # First match wins
    assert (
        discover_e3dc_entities({"export_to_grid": "g2", "consumption_from_grid": "g3"}).grid_export
        == "g2"
    )


def test_battery_capacity_fallback_chain() -> None:
    """battery_capacity fallback: system-battery-installed-capacity,
    installed_battery_capacity, battery_capacity."""
    assert (
        discover_e3dc_entities({"system-battery-installed-capacity": "c1"}).battery_capacity == "c1"
    )
    assert discover_e3dc_entities({"installed_battery_capacity": "c2"}).battery_capacity == "c2"
    assert discover_e3dc_entities({"battery_capacity": "c3"}).battery_capacity == "c3"


def test_max_charge_power_fallback_chain() -> None:
    """max_charge_power fallback: system-battery-charge-max,
    system_maximum_charge, maximum_charge, max_charge_power."""
    assert discover_e3dc_entities({"system-battery-charge-max": "m1"}).max_charge_power == "m1"
    assert discover_e3dc_entities({"system_maximum_charge": "m2"}).max_charge_power == "m2"
    assert discover_e3dc_entities({"maximum_charge": "m3"}).max_charge_power == "m3"
    assert discover_e3dc_entities({"max_charge_power": "m4"}).max_charge_power == "m4"


def test_battery_charge_fallback_chain() -> None:
    """battery_charge tries: battery-charge > battery_charge."""
    assert discover_e3dc_entities({"battery-charge": "b1"}).battery_charge == "b1"
    assert discover_e3dc_entities({"battery_charge": "b2"}).battery_charge == "b2"


def test_pv_power_fallback_chain() -> None:
    """pv_power tries: pv_power > solar-production."""
    assert discover_e3dc_entities({"pv_power": "p1"}).pv_power == "p1"
    assert discover_e3dc_entities({"solar-production": "p2"}).pv_power == "p2"


def test_house_power_fallback_chain() -> None:
    """house_power tries: house_power > house-consumption."""
    assert discover_e3dc_entities({"house_power": "h1"}).house_power == "h1"
    assert discover_e3dc_entities({"house-consumption": "h2"}).house_power == "h2"


# ======================================================================
# source_by_key_from_unique_ids
# ======================================================================


def test_registry_unique_ids_are_normalized_to_source_key_mapping() -> None:
    """Existing test — legacy unique_id suffixes."""
    source_by_key = source_by_key_from_unique_ids(
        {
            "serial_soc": "sensor.e3dc_soc",
            "serial_solar-production": "sensor.e3dc_solar",
            "serial_house-consumption": "sensor.e3dc_house",
            "serial_unrelated": "sensor.e3dc_unrelated",
        }
    )

    assert source_by_key == {
        "soc": "sensor.e3dc_soc",
        "solar-production": "sensor.e3dc_solar",
        "house-consumption": "sensor.e3dc_house",
    }


def test_source_by_key_mixed_legacy_and_actual() -> None:
    """Mixed legacy + actual suffix keys in unique_ids — maps to e3dc keys.

    Note: source_key_from_unique_id returns the e3dc TARGET key (value of
    _ACTUAL_SUFFIX_MAP), not the original suffix.  So multiple suffixes
    can resolve to the same e3dc key, causing overwrites in the returned
    dict.  Only suffixes that are KEYS in _ACTUAL_SUFFIX_MAP will match;
    values (e3dc target keys) are not matched as suffixes.
    """
    source_by_key = source_by_key_from_unique_ids(
        {
            "serial_soc": "sensor.e3dc_soc",
            "serial_solar-production": "sensor.e3dc_pv",
            "serial_house-consumption": "sensor.e3dc_house",
            "serial_export_to_grid": "sensor.e3dc_export",
            "serial_battery_charge": "sensor.e3dc_batt",
            "serial_state_of_charge": "sensor.e3dc_soc2",
        }
    )
    # serial_state_of_charge → 'soc' (same as serial_soc), so 'soc' is overwritten
    # serial_export_to_grid → 'grid_export' (the e3dc target key)
    assert source_by_key == {
        "soc": "sensor.e3dc_soc2",
        "solar-production": "sensor.e3dc_pv",
        "house-consumption": "sensor.e3dc_house",
        "grid_export": "sensor.e3dc_export",
        "battery_charge": "sensor.e3dc_batt",
    }


def test_source_by_key_empty() -> None:
    """Empty input produces empty output."""
    assert source_by_key_from_unique_ids({}) == {}


def test_source_by_key_no_false_positives() -> None:
    """Values of _ACTUAL_SUFFIX_MAP (e3dc target keys) should NOT match as unique_id suffixes."""
    # pv_power is a VALUE (target e3dc key) not a KEY (suffix) in _ACTUAL_SUFFIX_MAP
    # so unique_ids ending with _pv_power should NOT be matched
    source_by_key = source_by_key_from_unique_ids(
        {
            "serial_pv_power": "sensor.e3dc_pv",
            "serial_house_power": "sensor.e3dc_house",
            "serial_soc": "sensor.e3dc_real",
        }
    )
    # Only 'soc' is a recognised suffix; pv_power and house_power are not
    assert source_by_key == {
        "soc": "sensor.e3dc_real",
    }
