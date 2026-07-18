from custom_components.universal_energy_manager.e3dc_rscp import source_by_key_from_unique_ids


def test_registry_unique_ids_are_normalized_to_source_key_mapping() -> None:
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
