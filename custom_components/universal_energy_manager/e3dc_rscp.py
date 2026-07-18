"""Discovery helpers for the existing hacs-e3dc / e3dc_rscp integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

_SOURCE_KEYS = frozenset(
    {
        "soc",
        "solar-production",
        "house-consumption",
        "grid-production",
        "battery-charge",
        "system-battery-installed-capacity",
        "system-battery-charge-max",
    }
)


def source_key_from_unique_id(unique_id: str) -> str | None:
    """Extract a known e3dc_rscp sensor key from its stable unique ID."""
    for key in _SOURCE_KEYS:
        if unique_id.endswith(f"_{key}"):
            return key
    return None


def uem_identity_from_source(source_unique_id: str | None, source_entry_id: str) -> str:
    """Derive a stable UEM identity from the E3DC hardware ID when available."""
    return f"e3dc_rscp:{source_unique_id or source_entry_id}"


def source_by_key_from_unique_ids(entity_id_by_unique_id: Mapping[str, str]) -> dict[str, str]:
    """Build the stable source-key map from entity-registry records."""
    return {
        key: entity_id
        for unique_id, entity_id in entity_id_by_unique_id.items()
        if (key := source_key_from_unique_id(unique_id)) is not None
    }


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
