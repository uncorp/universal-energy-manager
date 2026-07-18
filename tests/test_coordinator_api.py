from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry

from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator


def test_shadow_coordinator_constructs_with_home_assistant_2024_api() -> None:
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain="universal_energy_manager",
        title="UEM",
        data={},
        source="user",
        entry_id="uem-entry",
    )

    coordinator = UemShadowCoordinator(MagicMock(), entry)

    assert coordinator.name == "universal_energy_manager"
