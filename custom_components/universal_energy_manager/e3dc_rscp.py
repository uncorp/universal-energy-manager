"""Discovery helpers for the existing hacs-e3dc / e3dc_rscp integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Legacy keys (hacs-e3dc / e3dc_rscp v1.x — deprecated, kept for compat)
_LEGACY_KEYS = frozenset(
    {
        "soc",
        "solar-production",
        "house-consumption",
        "grid-netchange",
        "battery-charge",
        "system-battery-installed-capacity",
        "system-battery-charge-max",
    }
)

# Actual entity naming used by hacs-e3dc/e3dc_rscp on S10E Pro and similar devices.
# These suffixes appear in the entity_id (and typically in the unique_id).
# Mapping to internal e3dc_rscp sensor keys (used by discover_e3dc_entities).
_ACTUAL_SUFFIX_MAP: dict[str, str] = {
    "state_of_charge": "soc",
    "solar_production": "pv_power",
    "house_consumption": "house_power",
    "consumption_from_grid": "grid_export",
    "export_to_grid": "grid_export",
    "battery_charge": "battery_charge",
    "battery_discharge": "battery_discharge",
    "installed_battery_capacity": "battery_capacity",
    "system_maximum_charge": "max_charge_power",
    "maximum_charge": "max_charge_power",
    "system_maximum_discharge": "max_discharge_power",
    "maximum_discharge": "max_discharge_power",
    "derate_feed_above": "derate_feed_above",
    "autarky": "autarky",
    "self_consumption": "self_consumption",
    "energy_charged_from_grid": "energy_charged_from_grid",
    "mode": "mode",
    "current_operation_mode": "current_operation_mode",
    "current_power_value": "current_power_value",
    "sg_ready": "sg_ready",
    "additional_total": "additional_total",
    "additional": "additional",
    "additional_consumption_total": "additional_consumption_total",
    "additional_consumption": "additional_consumption",
    "wallbox_consumption": "wallbox_consumption",
    "installed_peak_power": "installed_peak_power",
    "battery_charge_today": "battery_charge_today",
    "battery_discharge_today": "battery_discharge_today",
    "consumption_from_grid_today": "consumption_from_grid_today",
    "export_to_grid_today": "export_to_grid_today",
    "house_consumption_today": "house_consumption_today",
    "solar_production_today": "solar_production_today",
    "autarky_today": "autarky_today",
    "self_consumption_today": "self_consumption_today",
}

# Build _SOURCE_KEYS from _ACTUAL_SUFFIX_MAP values (union of all e3dc sensor keys)
_SOURCE_KEYS = frozenset(_ACTUAL_SUFFIX_MAP.values())


def source_key_from_unique_id(unique_id: str) -> str | None:
    """Extract a known e3dc_rscp sensor key from its stable unique ID.

    Tries the actual entity naming suffixes first, then falls back to
    legacy hyphen-separated abbreviated keys for backward compatibility.
    """
    # Try actual naming suffixes (underscore-separated, full names).
    # Iterate in reverse so longer suffixes (e.g. "current_operation_mode")
    # match before shorter ones (e.g. "mode") that are their suffix.
    for suffix, e3dc_key in reversed(list(_ACTUAL_SUFFIX_MAP.items())):
        if unique_id.endswith(f"_{suffix}") or unique_id.endswith(suffix):
            return e3dc_key

    # Legacy fallback (hyphen-separated abbreviated keys)
    for key in _LEGACY_KEYS:
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
    # Extended keys (S10E Pro naming)
    battery_discharge: str | None = None
    derate_feed_above: str | None = None
    autarky: str | None = None
    self_consumption: str | None = None
    energy_charged_from_grid: str | None = None
    mode: str | None = None
    current_operation_mode: str | None = None
    current_power_value: str | None = None
    sg_ready: str | None = None
    additional_total: str | None = None
    additional: str | None = None
    additional_consumption_total: str | None = None
    additional_consumption: str | None = None
    wallbox_consumption: str | None = None
    installed_peak_power: str | None = None
    battery_charge_today: str | None = None
    battery_discharge_today: str | None = None
    consumption_from_grid_today: str | None = None
    export_to_grid_today: str | None = None
    house_consumption_today: str | None = None
    solar_production_today: str | None = None
    autarky_today: str | None = None
    self_consumption_today: str | None = None


def discover_e3dc_entities(source_by_key: Mapping[str, str]) -> E3dcEntityMap:
    """Map stable e3dc_rscp sensor keys to UEM's normalized live inputs.

    The source_by_key dict maps e3dc sensor keys to entity_ids.  These keys
    may come in two forms:

    1. Legacy hacs-e3dc / e3dc_rscp v1.x keys (e.g. ``"soc"``,
       ``"solar-production"``, ``"grid-netchange"``).
    2. Actual S10E Pro / newer keys (e.g. ``"soc"``, ``"pv_power"``,
       ``"house_power"``, ``"consumption_from_grid"``, ``"export_to_grid"``,
       ``"system_maximum_charge"``, ``"installed_battery_capacity"``).

    The function normalises to the UEM-facing key names.
    """
    # --- SOC ---
    soc = source_by_key.get("soc")

    # --- PV power ---
    pv_power = source_by_key.get("pv_power") or source_by_key.get("solar-production")

    # --- House power ---
    house_power = source_by_key.get("house_power") or source_by_key.get("house-consumption")

    # --- Grid export: try all known variants, including the already-normalized key ---
    grid_export = (
        source_by_key.get("grid-netchange")
        or source_by_key.get("export_to_grid")
        or source_by_key.get("consumption_from_grid")
        or source_by_key.get("grid_export")
    )

    # --- Battery charge ---
    battery_charge = (
        source_by_key.get("battery-charge")
        or source_by_key.get("battery_charge")
    )

    # --- Battery capacity ---
    battery_capacity = (
        source_by_key.get("system-battery-installed-capacity")
        or source_by_key.get("installed_battery_capacity")
        or source_by_key.get("battery_capacity")
    )

    # --- Max charge power ---
    max_charge_power = (
        source_by_key.get("system-battery-charge-max")
        or source_by_key.get("system_maximum_charge")
        or source_by_key.get("maximum_charge")
        or source_by_key.get("max_charge_power")
    )

    return E3dcEntityMap(
        soc=soc,
        pv_power=pv_power,
        house_power=house_power,
        grid_export=grid_export,
        battery_charge=battery_charge,
        battery_capacity=battery_capacity,
        max_charge_power=max_charge_power,
        battery_discharge=source_by_key.get("battery_discharge"),
        derate_feed_above=source_by_key.get("derate_feed_above"),
        autarky=source_by_key.get("autarky"),
        self_consumption=source_by_key.get("self_consumption"),
        energy_charged_from_grid=source_by_key.get("energy_charged_from_grid"),
        mode=source_by_key.get("mode"),
        current_operation_mode=source_by_key.get("current_operation_mode"),
        current_power_value=source_by_key.get("current_power_value"),
        sg_ready=source_by_key.get("sg_ready"),
        additional_total=source_by_key.get("additional_total"),
        additional=source_by_key.get("additional"),
        additional_consumption_total=source_by_key.get("additional_consumption_total"),
        additional_consumption=source_by_key.get("additional_consumption"),
        wallbox_consumption=source_by_key.get("wallbox_consumption"),
        installed_peak_power=source_by_key.get("installed_peak_power"),
        battery_charge_today=source_by_key.get("battery_charge_today"),
        battery_discharge_today=source_by_key.get("battery_discharge_today"),
        consumption_from_grid_today=source_by_key.get("consumption_from_grid_today"),
        export_to_grid_today=source_by_key.get("export_to_grid_today"),
        house_consumption_today=source_by_key.get("house_consumption_today"),
        solar_production_today=source_by_key.get("solar_production_today"),
        autarky_today=source_by_key.get("autarky_today"),
        self_consumption_today=source_by_key.get("self_consumption_today"),
    )
