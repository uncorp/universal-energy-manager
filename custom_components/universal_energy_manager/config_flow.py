"""Config flow for UEM's safe, Shadow-only first installation.

UEM is universal: e3dc_rscp is optional (auto-discovery / prefill only).
Manual entity mapping is always available and is the primary path.
Forecast.Solar is optional, Solar/PV-only, unlimited sources supported.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
)
from .e3dc_rscp import (
    discover_e3dc_entities,
    source_by_key_from_unique_ids,
    uem_identity_from_source,
)

_LOGGER = logging.getLogger(__name__)

_REQUIRED_FIELDS = (
    CONF_SOC_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
)

# Human-readable labels for the manual entity selection form
_ENTITY_LABELS = {
    CONF_SOC_ENTITY: "Battery State of Charge (SoC)",
    CONF_PV_POWER_ENTITY: "PV / Solar Power",
    CONF_HOUSE_POWER_ENTITY: "House Consumption",
    CONF_GRID_EXPORT_ENTITY: "Grid Export / Feed-in Power",
    CONF_BATTERY_CHARGE_ENTITY: "Battery Charge / Discharge Power",
    CONF_BATTERY_CAPACITY_ENTITY: "Battery Installed Capacity",
    CONF_MAX_CHARGE_POWER_ENTITY: "Maximum Battery Charge Power",
}


def _entity_options(
    hass, e3dc_entry_id: str | None = None, e3dc_map=None
) -> dict[str, str]:
    """Build a flat {entity_id → label} dict from the entity registry."""
    registry = er.async_get(hass)
    options: dict[str, str] = {}

    if e3dc_entry_id is not None:
        # Prefill with entities from the e3dc_rscp adapter
        e3dc_unique_ids = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(
                registry, e3dc_entry_id
            )
            if entry.domain == "sensor" and entry.unique_id is not None
        }
        e3dc_source_map = source_by_key_from_unique_ids(e3dc_unique_ids)
        if e3dc_map is None:
            e3dc_map = discover_e3dc_entities(e3dc_source_map)

        for conf_key in _REQUIRED_FIELDS:
            val = getattr(e3dc_map, conf_key, None)
            if val is not None:
                options[val] = f"{val} (auto-detected)"

    # Also add all other sensors (non-e3dc) so user can pick freely
    for entity_entry in registry.entities.values():
        if (
            entity_entry.domain == "sensor"
            and entity_entry.entity_id not in options
            and entity_entry.unique_id is not None
        ):
            options[entity_entry.entity_id] = entity_entry.entity_id

    # Also add custom / free-text entities that might not be in the registry yet
    for entity_id in list(options.keys()):
        state = hass.states.get(entity_id)
        if state is None:
            # Remove unavailable entities from suggestions
            options.pop(entity_id, None)

    return options


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
                            {"cancel": "Abbrechen – e3dc_rscp zuerst einrichten",
                             "continue": "Mit manueller Zuordnung fortfahren"}
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
        }
        self._prefill_data = entity_data

        missing = [
            field
            for field in _REQUIRED_FIELDS
            if not entity_data[field]
        ]

        if user_input is not None:
            # Collect confirmed values — prefer user input over prefill
            for field in _REQUIRED_FIELDS:
                if field in user_input and user_input[field]:
                    entity_data[field] = user_input[field]

            missing = [
                field
                for field in _REQUIRED_FIELDS
                if not entity_data[field]
            ]
            if missing:
                return self.async_show_form(
                    step_id="confirm",
                    errors={"base": "missing_required_entities"},
                    description_placeholders={
                        "missing": ", ".join(missing),
                        "detected": str(
                            sum(1 for v in entity_data.values() if v is not None)
                        ),
                    },
                    data_schema=vol.Schema(
                        self._build_entity_schema(entity_data, allow_empty=True)
                    ),
                )

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

        # Default: show form with prefill in data_schema (editable fields)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "detected": str(
                    sum(1 for v in entity_data.values() if v is not None)
                ),
                "missing": ", ".join(missing) if missing else "",
            },
            errors={"base": "missing_required_entities"} if missing else None,
            data_schema=vol.Schema(
                self._build_entity_schema(entity_data, allow_empty=bool(missing))
            ),
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
                data_schema=vol.Schema(
                    self._build_entity_schema(self._prefill_data)
                ),
            )

        # Validate all required fields are present
        entity_data = {}
        for field in _REQUIRED_FIELDS:
            val = user_input.get(field)
            if val is not None and val.strip():
                entity_data[field] = val.strip()

        missing = [
            field
            for field in _REQUIRED_FIELDS
            if field not in entity_data
        ]
        if missing:
            return self.async_show_form(
                step_id="manual_mapping",
                errors={"base": "missing_required_entities"},
                description_placeholders={"missing": ", ".join(missing)},
                data_schema=vol.Schema(
                    self._build_entity_schema(self._prefill_data)
                ),
            )

        # Collect optional forecast_solar entries
        forecast_solar_entry_ids = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(
                FORECAST_SOLAR_DOMAIN
            )
        ]

        # Generate a stable unique_id for manual entries (use flow ID as fallback)
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
            e3dc_info = "Kein Adapter konfiguriert" if is_manual else "e3dc_rscp Adapter vorhanden"

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
        do_edit = user_input.get("edit_manual", False)

        if do_edit:
            # Show edit form for manual entities
            return await self._show_reconfigure_edit(entry, current_data)

        if do_rescan:
            # Rescan e3dc_rscp for new entities, preserve manual overrides
            return await self._rescan_e3dc(entry, current_data)

        # No action taken — go back to reconfigure form
        return await self.async_step_reconfigure()

    async def _show_reconfigure_edit(
        self, entry: config_entries.ConfigEntry, current_data: dict
    ) -> FlowResult:
        """Show entity editing form in reconfigure mode."""
        entity_data = {}
        for field in _REQUIRED_FIELDS:
            val = current_data.get(field)
            if val:
                entity_data[field] = val

        return self.async_show_form(
            step_id="reconfigure_edit",
            data_schema=vol.Schema(
                self._build_entity_schema(entity_data, allow_empty=True)
            ),
        )

    async def _rescan_e3dc(
        self, entry: config_entries.ConfigEntry, current_data: dict
    ) -> FlowResult:
        """Rescan e3dc_rscp for new entities, only update fields that were
        not manually overridden."""
        e3dc_entry_id = current_data.get(CONF_E3DC_CONFIG_ENTRY_ID)

        # Check if e3dc_rscp entry still exists
        e3dc_entries = self.hass.config_entries.async_entries(
            E3DC_RSCP_DOMAIN
        )
        e3dc_source = next(
            (e for e in e3dc_entries if e.entry_id == e3dc_entry_id),
            None,
        )

        if e3dc_source is None:
            return self.async_abort(reason="e3dc_rscp_not_configured")

        # Discover new entities
        assert isinstance(e3dc_entry_id, str)
        e3dc_map = self._discover_entities(e3dc_entry_id)
        new_data = dict(current_data)

        # Only update fields that haven't been manually overridden
        for field in _REQUIRED_FIELDS:
            existing_val = current_data.get(field)
            discovered_val = getattr(e3dc_map, field, None)
            if discovered_val and not existing_val:
                # Auto-assign if nothing was set before
                new_data[field] = discovered_val
            # If existing_val is set, keep it (preserve manual values)

        self.hass.config_entries.async_update_entry(entry, data=new_data)
        return self.async_abort(reason="reconfigure_complete")

    def _get_current_entry(self) -> config_entries.ConfigEntry | None:
        """Get the ConfigEntry associated with this reconfigure flow."""
        # In HA, reconfigure flows have _get_context() with entry_id
        context = self.context or {}
        entry_id = context.get("entry_id")
        if entry_id is None:
            # Fallback: check _async_current_entries
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
        for field in _REQUIRED_FIELDS:
            # Default to the prefill value
            default_val = prefill.get(field) or ""

            schema[vol.Optional(field, default=default_val)] = vol.All(
                str, vol.Length(min=1 if not allow_empty else 0)
            )
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
