from custom_components.universal_energy_manager.sensor import SHADOW_STATUS


def test_shadow_status_is_explicit_about_not_sending_commands() -> None:
    assert SHADOW_STATUS == "Shadow – keine aktive Steuerung"
