from homeassistant.const import Platform

from custom_components.universal_energy_manager import PLATFORMS


def test_integration_exposes_only_shadow_sensors_initially() -> None:
    assert PLATFORMS == [Platform.SENSOR]
