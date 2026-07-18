import pytest

from custom_components.universal_energy_manager.normalization import power_to_w


def test_power_to_w_normalizes_watts_and_kilowatts() -> None:
    assert power_to_w("2500", "W") == 2500.0
    assert power_to_w("2.5", "kW") == 2500.0


def test_power_to_w_rejects_unknown_units() -> None:
    with pytest.raises(ValueError, match="unsupported power unit"):
        power_to_w("2.5", "MW")
