from custom_components.universal_energy_manager.config_flow import UemConfigFlow


def test_config_flow_is_versioned() -> None:
    assert UemConfigFlow.VERSION == 1
