"""Discovery helpers for the existing hacs-e3dc / e3dc_rscp integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class E3dcEntityMap:
    """Known E3DC source entities, prefilled but always confirmable in setup."""

    soc: str | None = None
    pv_power: str | None = None
    house_power: str | None = None
    grid_export: str | None = None
    battery_charge: str | None = None
    battery_capacity: str | None = None
    max_charge_power: str | None = None


def discover_e3dc_entities(source_by_key: Mapping[str, str]) -> E3dcEntityMap:
    """Map stable e3dc_rscp sensor keys to UEM's normalized live inputs."""
    return E3dcEntityMap(
        soc=source_by_key.get("soc"),
        pv_power=source_by_key.get("solar-production"),
        house_power=source_by_key.get("house-consumption"),
        grid_export=source_by_key.get("grid-production"),
        battery_charge=source_by_key.get("battery-charge"),
        battery_capacity=source_by_key.get("system-battery-installed-capacity"),
        max_charge_power=source_by_key.get("system-battery-charge-max"),
    )
