from custom_components.universal_energy_manager.e3dc_rscp import uem_identity_from_source


def test_uem_identity_prefers_stable_e3dc_hardware_identity() -> None:
    assert uem_identity_from_source("S10E-12345", "volatile-entry-id") == "e3dc_rscp:S10E-12345"
    assert uem_identity_from_source(None, "fallback-entry-id") == "e3dc_rscp:fallback-entry-id"
