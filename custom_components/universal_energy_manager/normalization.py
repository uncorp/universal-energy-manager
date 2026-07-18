"""Unit normalization for entity states consumed by UEM."""

from __future__ import annotations


def power_to_w(value: str | int | float, unit: str | None) -> float:
    """Normalize an E3DC/Home Assistant power state to watts without guessing units."""
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError("power state is not numeric") from err

    if unit == "W":
        return number
    if unit == "kW":
        return number * 1000.0
    raise ValueError(f"unsupported power unit: {unit}")
