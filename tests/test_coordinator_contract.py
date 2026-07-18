from custom_components.universal_energy_manager.coordinator import ShadowData


def test_shadow_data_never_reports_a_sent_command() -> None:
    data = ShadowData(
        status="Shadow – keine aktive Steuerung",
        decision="Keine PV-Prognose verbunden",
        planned_charge_limit_w=0.0,
        error=None,
    )

    assert data.commands_sent is False
