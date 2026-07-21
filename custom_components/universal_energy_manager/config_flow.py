"""Config flow for UEM's safe, Shadow-only first installation.

UEM is universal: e3dc_rscp is optional (auto-discovery / prefill only).
Manual entity mapping is always available and is the primary path.
Forecast.Solar is optional, Solar/PV-only, unlimited sources supported.

New in v0.1.2:
- Battery capacity: entity in kWh OR manual kWh value
- Max charge power: entity in W OR manual W value
- Battery power: signed entity with explicit sign convention OR separate charge/discharge
- Grid power: signed entity with explicit sign convention OR separate import/export
- No direction guessing — always explicit
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import (
    _ENT_MAP_LOOKUP,
    BATTERY_POWER_MODE_SEPARATE,
    BATTERY_POWER_MODE_SIGNED,
    BATTERY_POWER_MODES,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_BATTERY_POWER_MODE,
    CONF_BATTERY_POWER_SIGN_CONVENTION,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_POWER_MODE,
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
    GRID_POWER_MODE_SEPARATE,
    GRID_POWER_MODE_SIGNED,
    GRID_POWER_MODES,
    SIGNED_CONVENTION_NEG_CHARGE_EXPORT,
    SIGNED_CONVENTION_NEG_DISCHARGE_IMPORT,
    SIGNED_CONVENTION_POS_CHARGE_EXPORT,
    SIGNED_CONVENTION_POS_DISCHARGE_IMPORT,
)
from .e3dc_rscp import (
    discover_e3dc_entities,
    source_by_key_from_unique_ids,
    uem_identity_from_source,
)

_LOGGER = logging.getLogger(__name__)

# Core required entities (always needed, regardless of power mode)
_CORE_REQUIRED = (
    CONF_SOC_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
)

# Backward-compatible alias for tests that reference _REQUIRED_FIELDS
_REQUIRED_FIELDS = _CORE_REQUIRED

# Human-readable labels for the manual entity selection form
_ENTITY_LABELS = {
    CONF_SOC_ENTITY: "Battery State of Charge (SoC)",
    CONF_PV_POWER_ENTITY: "PV / Solar Power",
    CONF_HOUSE_POWER_ENTITY: "House Consumption",
    CONF_GRID_EXPORT_ENTITY: "Grid Export / Feed-in Power",
    CONF_GRID_IMPORT_ENTITY: "Grid Import / Consumption from Grid",
    CONF_BATTERY_CHARGE_ENTITY: "Battery Charge Power",
    CONF_BATTERY_DISCHARGE_ENTITY: "Battery Discharge Power",
    CONF_BATTERY_CAPACITY_ENTITY: "Battery Installed Capacity",
    CONF_MAX_CHARGE_POWER_ENTITY: "Maximum Battery Charge Power",
    CONF_BATTERY_MANUAL_CAPACITY_KWH: "Battery Installed Capacity (kWh, manuell)",
    CONF_MAX_CHARGE_MANUAL_POWER_W: "Max. Charge Power (W, manuell)",
}

# Labels for power-mode dropdowns
_POWER_MODE_LABELS = {
    BATTERY_POWER_MODE_SIGNED: "Vorzeichen-behaftete Entität (ein Sensor, Vorzeichen wählen)",
    BATTERY_POWER_MODE_SEPARATE: "Getrennte Entitäten (Laden + Entladen)",
}

_GRID_MODE_LABELS = {
    GRID_POWER_MODE_SIGNED: "Vorzeichen-behaftete Entität (ein Sensor, Vorzeichen wählen)",
    GRID_POWER_MODE_SEPARATE: "Getrennte Entitäten (Bezug + Einspeisung)",
}

_SIGN_CONVENTION_LABELS = {
    SIGNED_CONVENTION_POS_CHARGE_EXPORT: "Positiv = Laden / Einspeisen",
    SIGNED_CONVENTION_NEG_CHARGE_EXPORT: "Negativ = Laden / Einspeisen",
    SIGNED_CONVENTION_POS_DISCHARGE_IMPORT: "Positiv = Entladen / Bezug",
    SIGNED_CONVENTION_NEG_DISCHARGE_IMPORT: "Negativ = Entladen / Bezug",
}


class UemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure UEM as a Shadow-only integration.

    Universal flow:
    1. Check for existing UEM entry → abort if already configured
    2. Look for e3dc_rscp entries
       - None: show no_e3dc_choice form (cancel or continue with manual)
       - One:  go to confirm step with prefill from e3dc
       - Many: show user selection form first
    3. confirm step: show discovered entities, user can edit or go to manual
    4. manual_mapping step: free-form entity selection (always available)
    5. create entry
    """

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize transient flow state."""
        self._e3dc_entry_id: str | None = None
        self._e3dc_map = None
        self._prefill_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------ #
    # User step: entry point                                               #
    # ------------------------------------------------------------------ #

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Entry point: check existing entries and decide next step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        entries = self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)

        if not entries:
            # No e3dc_rscp → show choice form instead of abort
            return self.async_show_form(
                step_id="no_e3dc_choice",
                data_schema=vol.Schema(
                    {
                        vol.Required("confirm"): vol.In(
                            {
                                "cancel": "Abbrechen – e3dc_rscp zuerst einrichten",
                                "continue": "Mit manueller Zuordnung fortfahren",
                            }
                        )
                    }
                ),
            )

        if len(entries) == 1:
            self._e3dc_entry_id = entries[0].entry_id
            return await self.async_step_confirm()

        # Multiple entries: show selection form
        if user_input is not None:
            self._e3dc_entry_id = user_input[CONF_E3DC_CONFIG_ENTRY_ID]
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_E3DC_CONFIG_ENTRY_ID): vol.In(
                        {entry.entry_id: entry.title for entry in entries}
                    )
                }
            ),
        )

    # ------------------------------------------------------------------ #
    # No-E3DC choice step                                                  #
    # ------------------------------------------------------------------ #

    async def async_step_no_e3dc_choice(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Present the user with a clear choice when no e3dc_rscp is found."""
        if user_input is None:
            return self.async_show_form(
                step_id="no_e3dc_choice",
                description_placeholders={},
            )

        choice = user_input.get("confirm")
        if choice == "cancel":
            return self.async_abort(
                reason="e3dc_rscp_optional_cancel",
                description_placeholders={},
            )

        # "continue" → go to manual mapping
        # Start with empty prefill (no adapter available)
        self._prefill_data = {}
        return await self.async_step_manual_mapping()

    # ------------------------------------------------------------------ #
    # Confirm step: e3dc_rscp discovered                                   #
    # ------------------------------------------------------------------ #

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Show detected entities and create a Shadow-only entry after confirmation."""
        # If _e3dc_entry_id is None we came from no_e3dc_choice → skip to manual
        if self._e3dc_entry_id is None:
            return await self.async_step_no_e3dc_choice()

        source_entry = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)
                if entry.entry_id == self._e3dc_entry_id
            ),
            None,
        )
        if source_entry is None:
            # Adapter was deleted or never existed — show the choice form
            # instead of aborting so the user can proceed with manual mapping.
            return await self.async_step_no_e3dc_choice()

        # Discover entities from the adapter
        self._e3dc_map = self._discover_entities(self._e3dc_entry_id)

        # Build entity data dict with discovered values as prefill
        entity_data = {
            CONF_SOC_ENTITY: self._e3dc_map.soc,
            CONF_PV_POWER_ENTITY: self._e3dc_map.pv_power,
            CONF_HOUSE_POWER_ENTITY: self._e3dc_map.house_power,
            CONF_GRID_EXPORT_ENTITY: self._e3dc_map.grid_export,
            CONF_BATTERY_CHARGE_ENTITY: self._e3dc_map.battery_charge,
            CONF_BATTERY_CAPACITY_ENTITY: self._e3dc_map.battery_capacity,
            CONF_MAX_CHARGE_POWER_ENTITY: self._e3dc_map.max_charge_power,
            CONF_BATTERY_POWER_MODE: BATTERY_POWER_MODE_SIGNED,
            CONF_BATTERY_POWER_SIGN_CONVENTION: SIGNED_CONVENTION_POS_CHARGE_EXPORT,
            CONF_GRID_POWER_MODE: GRID_POWER_MODE_SIGNED,
            CONF_GRID_POWER_SIGN_CONVENTION: SIGNED_CONVENTION_POS_CHARGE_EXPORT,
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_BATTERY_DISCHARGE_ENTITY: "",
            CONF_GRID_IMPORT_ENTITY: "",
        }
        self._prefill_data = entity_data

        if user_input is not None:
            # Collect confirmed values — prefer user input over prefill
            for field in list(entity_data.keys()):
                if field in user_input and isinstance(user_input[field], str):
                    val = user_input[field].strip() if user_input[field] else ""
                    entity_data[field] = val
                elif field in user_input:
                    entity_data[field] = user_input[field]

            # Collect optional forecast_solar entries
            forecast_solar_entry_ids = [
                entry.entry_id
                for entry in self.hass.config_entries.async_entries(
                    FORECAST_SOLAR_DOMAIN
                )
            ]

            await self.async_set_unique_id(
                uem_identity_from_source(
                    source_entry.unique_id, source_entry.entry_id
                )
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="UEM – Universal Energy Manager",
                data={
                    CONF_E3DC_CONFIG_ENTRY_ID: self._e3dc_entry_id,
                    CONF_E3DC_SOURCE_UNIQUE_ID: source_entry.unique_id,
                    CONF_FORECAST_SOLAR_ENTRY_IDS: forecast_solar_entry_ids,
                    CONF_MANUAL_ENTITIES: False,
                    **entity_data,
                },
            )

        # When NO core entities were detected, skip confirm and go straight to
        # manual_mapping so the user is not blocked on an empty form.
        detected_core = sum(
            1 for field in _CORE_REQUIRED
            if isinstance(entity_data.get(field), str) and entity_data.get(field, "").strip()
        )
        if detected_core == 0:
            return await self.async_step_manual_mapping()

        # Default: show form with prefill in data_schema (editable fields)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "detected": str(
                    sum(1 for v in entity_data.values() if isinstance(v, str) and v.strip())
                )
            },
            data_schema=vol.Schema(self._build_full_schema(entity_data)),
        )

    # ------------------------------------------------------------------ #
    # Manual mapping step: universal, always available                      #
    # ------------------------------------------------------------------ #

    async def async_step_manual_mapping(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Universal manual entity mapping — always available."""
        if self._prefill_data is None:
            self._prefill_data = {}

        if user_input is None:
            # Show the manual mapping form with prefill suggestions
            return self.async_show_form(
                step_id="manual_mapping",
                description_placeholders={
                    "detected": str(
                        sum(1 for v in self._prefill_data.values() if v)
                    )
                    if self._prefill_data
                    else "0"
                },
                data_schema=vol.Schema(self._build_full_schema(self._prefill_data)),
            )

        # Collect all values: start from prefill, then overlay user_input
        entity_data = dict(self._prefill_data) if self._prefill_data else {}
        for field in set(list(entity_data.keys()) + list(user_input.keys())):
            if field in user_input and isinstance(user_input[field], str):
                entity_data[field] = user_input[field].strip()
            elif field in user_input:
                entity_data[field] = user_input[field]
            elif field in entity_data:
                pass  # keep prefill value
            else:
                entity_data[field] = ""

        # Validate: core entities required
        for field in _CORE_REQUIRED:
            val = entity_data.get(field, "")
            if not val or (isinstance(val, str) and not val.strip()):
                return self.async_show_form(
                    step_id="manual_mapping",
                    errors={"base": "missing_required_entities"},
                    description_placeholders={
                        "missing": ", ".join(
                            f for f in _CORE_REQUIRED
                            if not entity_data.get(f, "")
                            or (
                                isinstance(entity_data.get(f, ""), str)
                                and not entity_data.get(f, "").strip()
                            )
                        )
                    },
                    data_schema=vol.Schema(self._build_full_schema(entity_data)),
                )

        # Validate battery capacity: either entity or manual kWh
        cap_entity = entity_data.get(CONF_BATTERY_CAPACITY_ENTITY, "")
        cap_manual = entity_data.get(CONF_BATTERY_MANUAL_CAPACITY_KWH, "")
        if not cap_entity or (isinstance(cap_entity, str) and not cap_entity.strip()):
            if not cap_manual or (isinstance(cap_manual, str) and not cap_manual.strip()):
                return self.async_show_form(
                    step_id="manual_mapping",
                    errors={"base": "missing_required_entities"},
                    description_placeholders={
                        "missing": CONF_BATTERY_CAPACITY_ENTITY
                    },
                    data_schema=vol.Schema(self._build_full_schema(entity_data)),
                )

        # Validate max charge power: either entity or manual W
        max_entity = entity_data.get(CONF_MAX_CHARGE_POWER_ENTITY, "")
        max_manual = entity_data.get(CONF_MAX_CHARGE_MANUAL_POWER_W, "")
        if not max_entity or (isinstance(max_entity, str) and not max_entity.strip()):
            if not max_manual or (isinstance(max_manual, str) and not max_manual.strip()):
                return self.async_show_form(
                    step_id="manual_mapping",
                    errors={"base": "missing_required_entities"},
                    description_placeholders={
                        "missing": CONF_MAX_CHARGE_POWER_ENTITY
                    },
                    data_schema=vol.Schema(self._build_full_schema(entity_data)),
                )

        # Validate battery power mode
        bat_mode = entity_data.get(CONF_BATTERY_POWER_MODE, "")
        if bat_mode not in (BATTERY_POWER_MODE_SIGNED, BATTERY_POWER_MODE_SEPARATE):
            entity_data[CONF_BATTERY_POWER_MODE] = BATTERY_POWER_MODE_SIGNED

        # Validate grid power mode
        grid_mode = entity_data.get(CONF_GRID_POWER_MODE, "")
        if grid_mode not in (GRID_POWER_MODE_SIGNED, GRID_POWER_MODE_SEPARATE):
            entity_data[CONF_GRID_POWER_MODE] = GRID_POWER_MODE_SIGNED

        # Collect optional forecast_solar entries
        forecast_solar_entry_ids = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(FORECAST_SOLAR_DOMAIN)
        ]

        # Generate a stable unique_id for manual entries
        config = getattr(self.hass, "config", None)
        location = getattr(config, "location", None)
        if location is not None:
            lat = getattr(location, "latitude", 0)
            lon = getattr(location, "longitude", 0)
            manual_uid = f"uem:manual:{lat:.4f},{lon:.4f}"
        else:
            manual_uid = f"uem:manual:flow:{id(self)}"
        await self.async_set_unique_id(manual_uid)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="UEM – Universal Energy Manager (Manual)",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_E3DC_SOURCE_UNIQUE_ID: None,
                CONF_FORECAST_SOLAR_ENTRY_IDS: forecast_solar_entry_ids,
                CONF_MANUAL_ENTITIES: True,
                **entity_data,
            },
        )

    # ------------------------------------------------------------------ #
    # Reconfigure step: rescan without overwriting                         #
    # ------------------------------------------------------------------ #

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Reconfigure existing UEM entry — rescan adapters, keep manual values."""
        entry = self._get_current_entry()
        if entry is None:
            return self.async_abort(reason="not_configured")

        current_data = dict(entry.data)

        if user_input is None:
            # Show current configuration with option to rescan
            is_manual = current_data.get(CONF_MANUAL_ENTITIES, False)
            e3dc_info = (
                "Kein Adapter konfiguriert" if is_manual else "e3dc_rscp Adapter vorhanden"
            )

            return self.async_show_form(
                step_id="reconfigure",
                description_placeholders={
                    "source": e3dc_info,
                    "manual": "Ja" if is_manual else "Nein",
                },
                data_schema=vol.Schema(
                    {
                        vol.Optional("rescan_e3dc", default=False): bool,
                        vol.Optional("edit_manual", default=False): bool,
                    }
                ),
            )

        do_rescan = user_input.get("rescan_e3dc", False)
        if isinstance(do_rescan, str):
            do_rescan = do_rescan.lower() in ("true", "1", "yes")
        do_edit = user_input.get("edit_manual", False)
        if isinstance(do_edit, str):
            do_edit = do_edit.lower() in ("true", "1", "yes")

        if do_edit:
            # Show edit form for manual entities
            return await self._show_reconfigure_edit(entry, current_data)

        if do_rescan:
            # Rescan e3dc_rscp for new entities, preserve manual overrides
            new_data = await self._rescan_e3dc(entry, current_data)
            if new_data is None:
                return self.async_abort(reason="e3dc_rscp_not_configured")
            return self.async_create_entry(
                title="UEM – Universal Energy Manager",
                data=new_data,
            )

        # No action taken — go back to reconfigure form
        return await self.async_step_reconfigure()

    async def _show_reconfigure_edit(
        self, entry: config_entries.ConfigEntry, current_data: dict
    ) -> FlowResult:
        """Show entity editing form in reconfigure mode."""
        entity_data = {}
        for key, val in current_data.items():
            entity_data[key] = str(val) if val is not None else ""

        return self.async_show_form(
            step_id="reconfigure_edit",
            data_schema=vol.Schema(self._build_full_schema(entity_data)),
        )

    async def _rescan_e3dc(
        self, entry: config_entries.ConfigEntry, current_data: dict
    ) -> dict | None:
        """Rescan e3dc_rscp for new entities, only update fields that were
        not manually overridden.

        Returns the new config data dict, or None if the e3dc entry is missing.
        """
        e3dc_entry_id = current_data.get(CONF_E3DC_CONFIG_ENTRY_ID)

        # Check if e3dc_rscp entry still exists
        e3dc_entries = self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)
        e3dc_source = next(
            (e for e in e3dc_entries if e.entry_id == e3dc_entry_id),
            None,
        )

        if e3dc_source is None:
            return None

        # Discover new entities
        assert isinstance(e3dc_entry_id, str)
        e3dc_map = self._discover_entities(e3dc_entry_id)
        new_data = dict(current_data)

        # Update only fields that were NOT manually set (empty or blank)
        for key, val in new_data.items():
            if not val or (isinstance(val, str) and not val.strip()):
                mapped = _ENT_MAP_LOOKUP.get(key)
                if mapped:
                    entity_val = getattr(e3dc_map, mapped, None)
                    if entity_val:
                        new_data[key] = entity_val

        return new_data

    def _get_current_entry(self) -> config_entries.ConfigEntry | None:
        """Get the ConfigEntry associated with this reconfigure flow."""
        context = self.context or {}
        entry_id = context.get("entry_id")
        if entry_id is None:
            current = self._async_current_entries()
            if current:
                return current[0]
            return None
        for ent in self.hass.config_entries.async_entries(DOMAIN):
            if ent.entry_id == entry_id:
                return ent
        return None

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _build_entity_schema(
        self,
        prefill: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> dict:
        """Build the entity selection schema for confirm or manual_mapping."""
        if prefill is None:
            prefill = {}

        schema = {}
        for field in _CORE_REQUIRED:
            default_val = prefill.get(field) or ""
            schema[vol.Optional(field, default=default_val)] = vol.All(
                str, vol.Length(min=1 if not allow_empty else 0)
            )
        return schema

    def _build_full_schema(self, prefill: dict[str, Any] | None = None) -> dict:
        """Build the complete manual mapping schema with all new fields."""
        if prefill is None:
            prefill = {}

        schema = {}

        # Core entities
        for field in _CORE_REQUIRED:
            default_val = prefill.get(field) or ""
            schema[vol.Optional(field, default=default_val)] = str

        # Grid export
        grid_export_def = prefill.get(CONF_GRID_EXPORT_ENTITY) or ""
        schema[
            vol.Optional(CONF_GRID_EXPORT_ENTITY, default=grid_export_def)
        ] = str

        # Battery mode
        bat_mode = prefill.get(CONF_BATTERY_POWER_MODE, BATTERY_POWER_MODE_SIGNED)
        schema[
            vol.Optional(CONF_BATTERY_POWER_MODE, default=bat_mode)
        ] = vol.In(BATTERY_POWER_MODES)

        # Battery sign convention (for signed mode)
        bat_sign = prefill.get(
            CONF_BATTERY_POWER_SIGN_CONVENTION, SIGNED_CONVENTION_POS_CHARGE_EXPORT
        )
        schema[
            vol.Optional(CONF_BATTERY_POWER_SIGN_CONVENTION, default=bat_sign)
        ] = str

        # Battery discharge (only shown when mode = separate)
        bat_discharge = prefill.get(CONF_BATTERY_DISCHARGE_ENTITY) or ""
        schema[
            vol.Optional(CONF_BATTERY_DISCHARGE_ENTITY, default=bat_discharge)
        ] = str

        # Battery capacity: entity
        cap_def = prefill.get(CONF_BATTERY_CAPACITY_ENTITY) or ""
        schema[
            vol.Optional(CONF_BATTERY_CAPACITY_ENTITY, default=cap_def)
        ] = str

        # Battery capacity: manual kWh
        cap_manual_def = prefill.get(CONF_BATTERY_MANUAL_CAPACITY_KWH) or ""
        schema[
            vol.Optional(CONF_BATTERY_MANUAL_CAPACITY_KWH, default=cap_manual_def)
        ] = str

        # Max charge power: entity
        max_def = prefill.get(CONF_MAX_CHARGE_POWER_ENTITY) or ""
        schema[
            vol.Optional(CONF_MAX_CHARGE_POWER_ENTITY, default=max_def)
        ] = str

        # Max charge power: manual W
        max_manual_def = prefill.get(CONF_MAX_CHARGE_MANUAL_POWER_W) or ""
        schema[
            vol.Optional(CONF_MAX_CHARGE_MANUAL_POWER_W, default=max_manual_def)
        ] = str

        # Grid mode
        grid_mode = prefill.get(CONF_GRID_POWER_MODE, GRID_POWER_MODE_SIGNED)
        schema[
            vol.Optional(CONF_GRID_POWER_MODE, default=grid_mode)
        ] = vol.In(GRID_POWER_MODES)

        # Grid sign convention (for signed mode)
        grid_sign = prefill.get(
            CONF_GRID_POWER_SIGN_CONVENTION, SIGNED_CONVENTION_POS_CHARGE_EXPORT
        )
        schema[
            vol.Optional(CONF_GRID_POWER_SIGN_CONVENTION, default=grid_sign)
        ] = str

        # Grid import (only shown when mode = separate)
        grid_import = prefill.get(CONF_GRID_IMPORT_ENTITY) or ""
        schema[
            vol.Optional(CONF_GRID_IMPORT_ENTITY, default=grid_import)
        ] = str

        return schema

    def _discover_entities(self, config_entry_id: str):
        """Read only source entities belonging to the selected e3dc_rscp entry."""
        registry = er.async_get(self.hass)
        unique_ids = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(
                registry, config_entry_id
            )
            if entry.domain == "sensor" and entry.unique_id is not None
        }
        return discover_e3dc_entities(source_by_key_from_unique_ids(unique_ids))
