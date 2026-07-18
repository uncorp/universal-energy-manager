import pytest

from custom_components.universal_energy_manager.normalization import power_to_w


def test_power_to_w_normalizes_watts_and_kilowatts() -> None:
    assert power_to_w("2500", "W") == 2500.0
    assert power_to_w("2.5", "kW") == 2500.0


def test_power_to_w_rejects_unknown_units() -> None:
    with pytest.raises(ValueError, match="unsupported power unit"):
        power_to_w("2.5", "MW")


def test_power_to_w_treats_none_unit_as_watts() -> None:
    assert power_to_w("1500", None) == 1500.0


def test_power_to_w_accepts_numeric_input() -> None:
    assert power_to_w(1500, "W") == 1500.0
    assert power_to_w(1.5, "kW") == 1500.0


def test_power_to_w_rejects_non_numeric_value() -> None:
    with pytest.raises(ValueError, match="not numeric"):
        power_to_w("abc", "W")
