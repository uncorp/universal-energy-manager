"""Regression verification for the open diff: S10E Pro naming + config_flow last_step."""

from custom_components.universal_energy_manager.e3dc_rscp import (
    _ACTUAL_SUFFIX_MAP,
    _LEGACY_KEYS,
    _SOURCE_KEYS,
    discover_e3dc_entities,
    source_by_key_from_unique_ids,
    source_key_from_unique_id,
)


class TestActualSuffixMap:
    """Verify _ACTUAL_SUFFIX_MAP covers the S10E Pro entity naming."""

    def test_state_of_charge_maps_to_soc(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["state_of_charge"] == "soc"

    def test_solar_production_maps_to_pv_power(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["solar_production"] == "pv_power"

    def test_house_consumption_maps_to_house_power(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["house_consumption"] == "house_power"

    def test_consumption_from_grid_maps_to_grid_export(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["consumption_from_grid"] == "grid_export"

    def test_export_to_grid_maps_to_grid_export(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["export_to_grid"] == "grid_export"

    def test_battery_charge_is_identity(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["battery_charge"] == "battery_charge"

    def test_battery_discharge_is_identity(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["battery_discharge"] == "battery_discharge"

    def test_installed_battery_capacity_maps_to_battery_capacity(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["installed_battery_capacity"] == "battery_capacity"

    def test_system_maximum_charge_maps_to_max_charge_power(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["system_maximum_charge"] == "max_charge_power"

    def test_maximum_charge_maps_to_max_charge_power(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["maximum_charge"] == "max_charge_power"

    def test_system_maximum_discharge_maps_to_max_discharge_power(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["system_maximum_discharge"] == "max_discharge_power"

    def test_autarky_is_identity(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["autarky"] == "autarky"

    def test_self_consumption_is_identity(self) -> None:
        assert _ACTUAL_SUFFIX_MAP["self_consumption"] == "self_consumption"


class TestLegacyKeys:
    """Verify _LEGACY_KEYS contains the original abbreviated keys."""

    def test_legacy_soc(self) -> None:
        assert "soc" in _LEGACY_KEYS

    def test_legacy_solar_production(self) -> None:
        assert "solar-production" in _LEGACY_KEYS

    def test_legacy_grid_netchange(self) -> None:
        assert "grid-netchange" in _LEGACY_KEYS

    def test_legacy_battery_charge(self) -> None:
        assert "battery-charge" in _LEGACY_KEYS


class TestSourceKeyFromUniqueId:
    """Verify source_key_from_unique_id handles both new and legacy naming."""

    def test_new_suffix_state_of_charge(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_state_of_charge") == "soc"

    def test_new_suffix_solar_production(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_solar_production") == "pv_power"

    def test_new_suffix_house_consumption(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_house_consumption") == "house_power"

    def test_new_suffix_consumption_from_grid(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_consumption_from_grid") == "grid_export"

    def test_new_suffix_export_to_grid(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_export_to_grid") == "grid_export"

    def test_new_suffix_battery_discharge(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_battery_discharge") == "battery_discharge"

    def test_new_suffix_autarky(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_autarky") == "autarky"

    def test_legacy_soc(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_soc") == "soc"

    def test_legacy_solar_production(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_solar-production") == "solar-production"

    def test_legacy_battery_charge(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_battery-charge") == "battery-charge"

    def test_unknown_suffix_returns_none(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_unknown_suffix") is None

    def test_unknown_legacy_returns_none(self) -> None:
        assert source_key_from_unique_id("e3dc_rscp:ABC_foo-bar") is None

    def test_suffix_without_underscore_prefix(self) -> None:
        # unique_id ends with just the suffix (no separator)
        assert source_key_from_unique_id("e3dc_rscp:ABC_soc") == "soc"
        assert source_key_from_unique_id("e3dc_rscp:ABC_state_of_charge") == "soc"


class TestDiscoverE3dcEntities:
    """Verify discover_e3dc_entities handles both key families."""

    def test_discovery_actual_naming(self) -> None:
        """S10E Pro / newer key naming."""
        result = discover_e3dc_entities(
            {
                "soc": "sensor.e3dc_state_of_charge",
                "pv_power": "sensor.e3dc_solar_production",
                "house_power": "sensor.e3dc_house_consumption",
                "consumption_from_grid": "sensor.e3dc_consumption_from_grid",
                "export_to_grid": "sensor.e3dc_export_to_grid",
                "battery_charge": "sensor.e3dc_battery_charge",
                "battery_discharge": "sensor.e3dc_battery_discharge",
                "installed_battery_capacity": "sensor.e3dc_installed_battery_capacity",
                "system_maximum_charge": "sensor.e3dc_system_maximum_charge",
                "derate_feed_above": "sensor.e3dc_derate_feed_above",
                "autarky": "sensor.e3dc_autarky",
                "self_consumption": "sensor.e3dc_self_consumption",
                "energy_charged_from_grid": "sensor.e3dc_energy_charged_from_grid",
                "mode": "sensor.e3dc_mode",
                "current_operation_mode": "sensor.e3dc_current_operation_mode",
                "current_power_value": "sensor.e3dc_current_power_value",
                "sg_ready": "sensor.e3dc_sg_ready",
                "additional_total": "sensor.e3dc_additional_total",
                "additional": "sensor.e3dc_additional",
                "additional_consumption_total": "sensor.e3dc_additional_consumption_total",
                "additional_consumption": "sensor.e3dc_additional_consumption",
                "wallbox_consumption": "sensor.e3dc_wallbox_consumption",
                "installed_peak_power": "sensor.e3dc_installed_peak_power",
                "battery_charge_today": "sensor.e3dc_battery_charge_today",
                "battery_discharge_today": "sensor.e3dc_battery_discharge_today",
                "consumption_from_grid_today": "sensor.e3dc_consumption_from_grid_today",
                "export_to_grid_today": "sensor.e3dc_export_to_grid_today",
                "house_consumption_today": "sensor.e3dc_house_consumption_today",
                "solar_production_today": "sensor.e3dc_solar_production_today",
                "autarky_today": "sensor.e3dc_autarky_today",
                "self_consumption_today": "sensor.e3dc_self_consumption_today",
            }
        )
        assert result.soc == "sensor.e3dc_state_of_charge"
        assert result.pv_power == "sensor.e3dc_solar_production"
        assert result.house_power == "sensor.e3dc_house_consumption"
        assert result.grid_export == "sensor.e3dc_export_to_grid"
        # export_to_grid is 2nd in or-chain
        assert result.battery_charge == "sensor.e3dc_battery_charge"
        assert result.battery_discharge == "sensor.e3dc_battery_discharge"
        assert result.battery_capacity == "sensor.e3dc_installed_battery_capacity"
        assert result.max_charge_power == "sensor.e3dc_system_maximum_charge"
        assert result.derate_feed_above == "sensor.e3dc_derate_feed_above"
        assert result.autarky == "sensor.e3dc_autarky"
        assert result.self_consumption == "sensor.e3dc_self_consumption"
        assert result.energy_charged_from_grid == "sensor.e3dc_energy_charged_from_grid"
        assert result.mode == "sensor.e3dc_mode"
        assert result.current_operation_mode == "sensor.e3dc_current_operation_mode"
        assert result.current_power_value == "sensor.e3dc_current_power_value"
        assert result.sg_ready == "sensor.e3dc_sg_ready"
        assert result.additional_total == "sensor.e3dc_additional_total"
        assert result.additional == "sensor.e3dc_additional"
        assert result.additional_consumption_total == "sensor.e3dc_additional_consumption_total"
        assert result.additional_consumption == "sensor.e3dc_additional_consumption"
        assert result.wallbox_consumption == "sensor.e3dc_wallbox_consumption"
        assert result.installed_peak_power == "sensor.e3dc_installed_peak_power"
        assert result.battery_charge_today == "sensor.e3dc_battery_charge_today"
        assert result.battery_discharge_today == "sensor.e3dc_battery_discharge_today"
        assert result.consumption_from_grid_today == "sensor.e3dc_consumption_from_grid_today"
        assert result.export_to_grid_today == "sensor.e3dc_export_to_grid_today"
        assert result.house_consumption_today == "sensor.e3dc_house_consumption_today"
        assert result.solar_production_today == "sensor.e3dc_solar_production_today"
        assert result.autarky_today == "sensor.e3dc_autarky_today"
        assert result.self_consumption_today == "sensor.e3dc_self_consumption_today"

    def test_discovery_legacy_naming(self) -> None:
        """Original hacs-e3dc / e3dc_rscp v1.x naming."""
        result = discover_e3dc_entities(
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
        assert result.soc == "sensor.e3dc_state_of_charge"
        assert result.pv_power == "sensor.e3dc_solar_production"
        assert result.house_power == "sensor.e3dc_house_consumption"
        assert result.grid_export == "sensor.e3dc_grid_netchange"
        assert result.battery_charge == "sensor.e3dc_battery_charge"
        assert result.battery_capacity == "sensor.e3dc_battery_capacity"
        assert result.max_charge_power == "sensor.e3dc_max_charge_power"

    def test_discovery_fallback_pv_power(self) -> None:
        """pv_power falls back to solar-production."""
        result = discover_e3dc_entities({"solar-production": "sensor.alt"})
        assert result.pv_power == "sensor.alt"

    def test_discovery_fallback_house_power(self) -> None:
        """house_power falls back to house-consumption."""
        result = discover_e3dc_entities({"house-consumption": "sensor.alt"})
        assert result.house_power == "sensor.alt"

    def test_discovery_fallback_grid_export(self) -> None:
        """grid_export tries all known variants."""
        result = discover_e3dc_entities({"grid_export": "sensor.g"})
        assert result.grid_export == "sensor.g"
        result2 = discover_e3dc_entities({"export_to_grid": "sensor.g2"})
        assert result2.grid_export == "sensor.g2"
        result3 = discover_e3dc_entities({"grid-netchange": "sensor.g3"})
        assert result3.grid_export == "sensor.g3"

    def test_discovery_fallback_battery_capacity(self) -> None:
        """battery_capacity tries installed_battery_capacity."""
        result = discover_e3dc_entities({"installed_battery_capacity": "sensor.cap"})
        assert result.battery_capacity == "sensor.cap"

    def test_discovery_fallback_max_charge_power(self) -> None:
        """max_charge_power tries system_maximum_charge and maximum_charge."""
        result = discover_e3dc_entities(
            {
                "system_maximum_charge": "sensor.mc",
            }
        )
        assert result.max_charge_power == "sensor.mc"
        result2 = discover_e3dc_entities({"maximum_charge": "sensor.mc2"})
        assert result2.max_charge_power == "sensor.mc2"


class TestSourceByKeyFromUniqueIds:
    """Verify source_by_key_from_unique_ids normalizes new naming to source keys."""

    def test_normalizes_actual_suffixes(self) -> None:
        sources = source_by_key_from_unique_ids(
            {
                "e3dc_rscp:ABC_state_of_charge": "sensor.e3dc_soc",
                "e3dc_rscp:ABC_solar_production": "sensor.e3dc_pv",
                "e3dc_rscp:ABC_unknown": "sensor.e3dc_unknown",
            }
        )
        assert sources == {
            "soc": "sensor.e3dc_soc",
            "pv_power": "sensor.e3dc_pv",
        }

    def test_ignores_unknown_suffixes(self) -> None:
        sources = source_by_key_from_unique_ids(
            {
                "e3dc_rscp:ABC_foo_bar": "sensor.e3dc_foo",
            }
        )
        assert sources == {}


class TestSourceKeysUnion:
    """Verify _SOURCE_KEYS is built correctly from _ACTUAL_SUFFIX_MAP."""

    def test_source_keys_contains_soc(self) -> None:
        assert "soc" in _SOURCE_KEYS

    def test_source_keys_contains_pv_power(self) -> None:
        assert "pv_power" in _SOURCE_KEYS

    def test_source_keys_contains_battery_discharge(self) -> None:
        assert "battery_discharge" in _SOURCE_KEYS

    def test_source_keys_contains_autarky(self) -> None:
        assert "autarky" in _SOURCE_KEYS

    def test_source_keys_is_frozenset(self) -> None:
        assert isinstance(_SOURCE_KEYS, frozenset)

    def test_source_keys_uses_actual_map_values(self) -> None:
        """_SOURCE_KEYS should be exactly the values of _ACTUAL_SUFFIX_MAP."""
        assert _SOURCE_KEYS == frozenset(_ACTUAL_SUFFIX_MAP.values())

    def test_legacy_keys_subset_of_source_keys_via_suffix_map(self) -> None:
        """Legacy keys that have mapping should be in _SOURCE_KEYS."""
        # All values in _ACTUAL_SUFFIX_MAP are in _SOURCE_KEYS
        assert "soc" in _SOURCE_KEYS
        assert "pv_power" in _SOURCE_KEYS
