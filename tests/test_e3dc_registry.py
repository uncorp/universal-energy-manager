from custom_components.universal_energy_manager.e3dc_rscp import source_key_from_unique_id


def test_source_key_from_unique_id_only_accepts_known_e3dc_rscp_suffixes() -> None:
    assert source_key_from_unique_id("abc123_soc") == "soc"
    assert source_key_from_unique_id("abc123_solar-production") == "solar-production"
    assert source_key_from_unique_id("abc123_other") is None
