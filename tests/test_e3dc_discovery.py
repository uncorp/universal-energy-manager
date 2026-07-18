from custom_components.universal_energy_manager.e3dc_rscp import discover_e3dc_entities


def test_discovery_prefills_known_e3dc_rscp_measurements() -> None:
    discovered = discover_e3dc_entities(
        {
            "soc": "sensor.e3dc_state_of_charge",
            "solar-production": "sensor.e3dc_solar_production",
            "house-consumption": "sensor.e3dc_house_consumption",
            "grid-production": "sensor.e3dc_grid_export",
            "battery-charge": "sensor.e3dc_battery_charge",
            "system-battery-installed-capacity": "sensor.e3dc_battery_capacity",
            "system-battery-charge-max": "sensor.e3dc_max_charge_power",
        }
    )

    assert discovered.soc == "sensor.e3dc_state_of_charge"
    assert discovered.pv_power == "sensor.e3dc_solar_production"
    assert discovered.house_power == "sensor.e3dc_house_consumption"
    assert discovered.grid_export == "sensor.e3dc_grid_export"
    assert discovered.battery_charge == "sensor.e3dc_battery_charge"
    assert discovered.battery_capacity == "sensor.e3dc_battery_capacity"
    assert discovered.max_charge_power == "sensor.e3dc_max_charge_power"
