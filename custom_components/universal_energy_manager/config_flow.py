"""Config flow for UEM's safe, Shadow-only first installation.

UEM is universal: e3dc_rscp is optional (auto-discovery / prefill only).
Manual entity mapping is always available and is the primary path.
Forecast.Solar is optional, Solar/PV-only, unlimited sources supported.

New in v0.1.2:
- Battery capacity: entity in kWh OR manual kWh value
- Max charge power: entity in W OR manual W value
- Battery power: single signed entity (Batterieleistung)
- Grid power: single signed entity (Netzleistung) with sign convention
- Hausverbrauch: single entity, negative values allowed (e.g. Balkonkraftwerk)
- No direction guessing — always explicit
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import BooleanSelector

from .const import (
    _ENT_MAP_LOOKUP,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
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

# Core required entities (always needed, regardless of power mode)
_CORE_REQUIRED = (
    CONF_SOC_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
)

# Backward-compatible alias for tests that reference _REQUIRED_FIELDS
_REQUIRED_FIELDS = _CORE_REQUIRED


class UemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure UEM as a Shadow-only integration.

    Universal flow:
    1. Check for existing UEM entry → abort if already configured
    2. Look for e3dc_rscp entries
       - None: show no_e3dc_choice form (cancel or continue with manual)
       - One:  go to confirm step with prefill from e3dc
       - Many: show user selection form first
    3. confirm step: show detected entities, user can edit or go to manual
    4. manual_mapping step: free-form entity selection (always available)
    5. create entry

    Reconfigure:
    - If e3dc_config_entry_id stored: _rescan_e3dc → auto-save (existing path)
    - If e3dc_config_entry_id is None: rescan → 0 abort, 1 edit form
      with prefill, multiple → select → same prefill path
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
                                "continue": "Entitäten jetzt manuell zuordnen",
                                "later": "Später einrichten (sicherer Shadow-Modus)",
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

        # "later" persists an explicitly incomplete, safe Shadow entry.
        self._prefill_data = {}
        if choice == "later":
            return await self.async_step_manual_mapping({})

        # "continue" opens the optional one-page mapping form.
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
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            # hacs-e3dc's grid-netchange is positive for import and negative
            # for export; UEM normalizes to import-negative/export-positive.
            CONF_INVERT_GRID_POWER_SIGN: True,
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
        description_placeholders = {
            **self._build_description_placeholders(entity_data),
            "detected": str(
                sum(1 for v in entity_data.values() if isinstance(v, str) and v.strip())
            )
        }
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=description_placeholders,
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
                description_placeholders=self._build_description_placeholders(
                    self._prefill_data
                ),
                data_schema=vol.Schema(self._build_full_schema(self._prefill_data)),
            )

        # Keep every field optional. An incomplete entry is intentional: the
        # coordinator stays in safe Shadow status until it has enough data.
        entity_data = self._mapping_defaults()
        entity_data.update(self._prefill_data or {})
        for field, value in user_input.items():
            entity_data[field] = value.strip() if isinstance(value, str) else value

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

        if not do_rescan and not do_edit:
            # No action taken — go back to reconfigure form
            return await self.async_step_reconfigure()

        if do_edit:
            # Show edit form for manual entities — no discovery prefill for
            # plain edit (e3dc_map not needed when user just wants to edit)
            from .e3dc_rscp import E3dcEntityMap
            empty_map = E3dcEntityMap(
                soc=None, pv_power=None, house_power=None,
                grid_export=None, battery_charge=None,
                battery_capacity=None, max_charge_power=None,
            )
            return await self._show_reconfigure_edit(entry, current_data, empty_map)

        if do_rescan:
            e3dc_entry_id = current_data.get(CONF_E3DC_CONFIG_ENTRY_ID)
            if e3dc_entry_id is not None:
                # Existing path: e3dc entry ID stored → auto-save
                new_data = await self._rescan_e3dc(entry, current_data)
                if new_data is None:
                    return self.async_abort(reason="e3dc_rscp_not_configured")
                return self.async_create_entry(
                    title="UEM – Universal Energy Manager",
                    data=new_data,
                )
            else:
                # No entry ID stored — scan for existing adapters
                return await self.async_step_reconfigure_rescan()

    async def async_step_reconfigure_rescan(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Rescan for e3dc_rscp adapters when no e3dc_config_entry_id is stored.

        0 adapters: abort with e3dc_rscp_not_configured.
        1 adapter:   show reconfigure_edit form with prefill suggestions.
        Multiple:    show selection form; on selection → same prefill path.
        """
        e3dc_entries = self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)

        if not e3dc_entries:
            return self.async_abort(reason="e3dc_rscp_not_configured")

        if len(e3dc_entries) == 1:
            # Single adapter: discover entities and show edit form with prefill
            e3dc_entry = e3dc_entries[0]
            e3dc_map = self._discover_entities_from_entry(e3dc_entry.entry_id)
            entry = self._get_current_entry()
            return await self._show_reconfigure_edit(
                entry, dict(entry.data), e3dc_map
            )

        # Multiple adapters: show selection form
        if user_input is not None:
            self._e3dc_entry_id = user_input[CONF_E3DC_CONFIG_ENTRY_ID]
            e3dc_entry = next(
                (e for e in e3dc_entries if e.entry_id == self._e3dc_entry_id), None
            )
            if e3dc_entry is not None:
                e3dc_map = self._discover_entities_from_entry(e3dc_entry.entry_id)
                entry = self._get_current_entry()
                return await self._show_reconfigure_edit(
                    entry, dict(entry.data), e3dc_map
                )

        return self.async_show_form(
            step_id="reconfigure_rescan",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_E3DC_CONFIG_ENTRY_ID): vol.In(
                        {entry.entry_id: entry.title for entry in e3dc_entries}
                    )
                }
            ),
        )

    async def _show_reconfigure_edit(
        self,
        entry: config_entries.ConfigEntry,
        current_data: dict,
        e3dc_map: Any,
    ) -> FlowResult:
        """Show entity editing form in reconfigure mode.

        Discovery prefill is applied ONLY to fields that are blank in the
        current entry data.  Non-blank manual values are never overwritten.
        """
        # Build prefill: discovery values only for blank fields
        self._prefill_data = self._fill_blank_fields(e3dc_map, current_data)

        # Schema defaults: start from current data, then fill only blanks
        schema_defaults = {}
        for key in self._mapping_defaults().keys():
            cur = current_data.get(key, "")
            if not cur or (isinstance(cur, str) and not cur.strip()):
                p = self._prefill_data.get(key, "")
                schema_defaults[key] = p
            else:
                schema_defaults[key] = cur

        # Add non-mapping keys (sign convention, etc.) as-is
        for key, val in current_data.items():
            if key not in schema_defaults:
                schema_defaults[key] = str(val) if val is not None else ""

        return self.async_show_form(
            step_id="reconfigure_edit",
            description_placeholders=self._build_description_placeholders(
                self._prefill_data
            ),
            data_schema=vol.Schema(self._build_full_schema(schema_defaults)),
        )

    async def async_step_reconfigure_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Save a complete or intentionally incomplete manual mapping."""
        entry = self._get_current_entry()
        if entry is None:
            return self.async_abort(reason="not_configured")
        if user_input is None:
            from .e3dc_rscp import E3dcEntityMap
            empty_map = E3dcEntityMap(
                soc=None, pv_power=None, house_power=None,
                grid_export=None, battery_charge=None,
                battery_capacity=None, max_charge_power=None,
            )
            return await self._show_reconfigure_edit(entry, dict(entry.data), empty_map)

        updated_data = self._mapping_defaults()
        # Merge existing entry data (preserves non-entity fields)
        updated_data.update(entry.data)
        # Apply user input (overrides everything — prefill was already baked
        # into the schema defaults above, so we do NOT apply _prefill_data here)
        for field, value in user_input.items():
            updated_data[field] = value.strip() if isinstance(value, str) else value

        return self.async_update_reload_and_abort(
            entry,
            data=updated_data,
            reason="reconfigure_successful",
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

    def _discover_entities_from_entry(self, config_entry_id: str):
        """Discover e3dc_rscp entities from a specific entry's entity registry."""
        registry = er.async_get(self.hass)
        unique_ids = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(
                registry, config_entry_id
            )
            if entry.domain == "sensor" and entry.unique_id is not None
        }
        return discover_e3dc_entities(source_by_key_from_unique_ids(unique_ids))

    def _fill_blank_fields(
        self, e3dc_map, current_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fill only blank mapping fields from discovery, return entity_data dict.

        Returns a dict with all mapping keys.  Only fields that are empty/None/
        whitespace in *current_data* receive a discovery prefill.  Non-blank
        existing values are never overwritten.
        """
        defaults = {
            CONF_SOC_ENTITY: "",
            CONF_PV_POWER_ENTITY: "",
            CONF_HOUSE_POWER_ENTITY: "",
            CONF_GRID_EXPORT_ENTITY: "",
            CONF_BATTERY_CHARGE_ENTITY: "",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_INVERT_GRID_POWER_SIGN: False,
        }

        # Start from defaults, then overlay existing non-blank values
        entity_data = dict(defaults)
        if current_data:
            entity_data.update(current_data)

        for key, default_val in defaults.items():
            cur = entity_data.get(key, default_val)
            # Only fill when current value is empty / None / whitespace
            if not cur or (isinstance(cur, str) and not cur.strip()):
                mapped = _ENT_MAP_LOOKUP.get(key)
                if mapped:
                    entity_val = getattr(e3dc_map, mapped, None)
                    if entity_val:
                        entity_data[key] = entity_val

        return entity_data

    def _build_description_placeholders(
        self, prefill: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """Return a description_placeholders dict for HA 2024.3.x rendering.

        HA 2024.3.3 does NOT support ``data_description`` in config_flow
        strings.json — that was added in 2024.7+.  For this pinned version,
        per-field descriptions are delivered via the ``description`` field
        in strings.json together with ``description_placeholders`` passed
        to ``async_show_form()``.  The placeholders are substituted by the
        HA frontend at render time.

        Returns keys like ``soc_entity_desc``, ``house_power_entity_desc``,
        etc., with German explanation text.
        """
        return {
            "soc_entity_desc": (
                "Batterieladestand (SoC): Die Entität, die den aktuellen "
                "Ladestand der Batterie meldet (z. B. 50 = 50 %)."
            ),
            "pv_power_entity_desc": (
                "PV-Leistung: Die Entität der PV-Anlage, die die aktuelle "
                "erzeugte Leistung meldet."
            ),
            "house_power_entity_desc": (
                "Hausverbrauch: Die Entität des Hausverbrauchs. Ein negativer "
                "Wert ist zulässig und bedeutet, dass z. B. ein "
                "Balkonkraftwerk momentan mehr produziert als das Haus "
                "verbraucht."
            ),
            "battery_charge_entity_desc": (
                "Batterieleistung: Die Entität der Batterieleistung. Ein "
                "einziger Sensor, der je nach Richtung (laden/entladen) "
                "positive oder negative Werte liefern kann."
            ),
            "battery_capacity_entity_desc": (
                "Batteriekapazität (Entität): Die Entität, die die installierte "
                "Batteriekapazität in kWh meldet. Optional — alternativ kannst "
                "du einen festen Wert eingeben."
            ),
            "battery_manual_capacity_kwh_desc": (
                "Batteriekapazität (fester Wert): Die installierte "
                "Batteriekapazität als fester Wert in kWh. Optional — "
                "alternativ kannst du eine Entität wählen."
            ),
            "max_charge_power_entity_desc": (
                "Max. Ladeleistung (Entität): Die Entität, die die maximale "
                "Ladeleistung der Batterie in Watt meldet. Optional — "
                "alternativ kannst du einen festen Wert eingeben."
            ),
            "max_charge_manual_power_w_desc": (
                "Max. Ladeleistung (fester Wert): Die maximale Ladeleistung "
                "als fester Wert in Watt. Optional — alternativ kannst du "
                "eine Entität wählen."
            ),
            "grid_export_entity_desc": (
                "Netzleistung: Die Entität der Netzleistung. Ein einzelner "
                "Sensor, der Import und Export über eine einzige Zahl "
                "abbildet."
            ),
            "invert_grid_power_sign_desc": (
                "Vorzeichen der Netzleistung umkehren: Bei automatisch erkanntem "
                "e3dc_rscp ist dies standardmäßig aktiviert, weil dessen "
                "grid-netchange Netzbezug positiv und Einspeisung negativ "
                "meldet. Nur für abweichende Quellen umstellen."
            ),
        }

    def _mapping_defaults(self) -> dict[str, Any]:
        """Return the complete optional manual-mapping data shape."""
        return {
            CONF_SOC_ENTITY: "",
            CONF_PV_POWER_ENTITY: "",
            CONF_HOUSE_POWER_ENTITY: "",
            CONF_BATTERY_CHARGE_ENTITY: "",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_GRID_EXPORT_ENTITY: "",
            CONF_INVERT_GRID_POWER_SIGN: False,
        }

    def _build_full_schema(self, prefill: dict[str, Any] | None = None) -> dict:
        """Build one optional, grouped manual-mapping form."""
        values = self._mapping_defaults()
        values.update(prefill or {})

        return {
            # Allgemeine Messwerte
            vol.Optional(CONF_SOC_ENTITY, default=values[CONF_SOC_ENTITY]): str,
            vol.Optional(CONF_PV_POWER_ENTITY, default=values[CONF_PV_POWER_ENTITY]): str,
            vol.Optional(CONF_HOUSE_POWER_ENTITY, default=values[CONF_HOUSE_POWER_ENTITY]): str,
            # Batterie: alle Batterie-Felder zusammen und optional.
            vol.Optional(
                CONF_BATTERY_CHARGE_ENTITY,
                default=values[CONF_BATTERY_CHARGE_ENTITY],
            ): str,
            vol.Optional(
                CONF_BATTERY_CAPACITY_ENTITY,
                default=values[CONF_BATTERY_CAPACITY_ENTITY],
            ): str,
            vol.Optional(
                CONF_BATTERY_MANUAL_CAPACITY_KWH,
                default=values[CONF_BATTERY_MANUAL_CAPACITY_KWH],
            ): str,
            vol.Optional(
                CONF_MAX_CHARGE_POWER_ENTITY,
                default=values[CONF_MAX_CHARGE_POWER_ENTITY],
            ): str,
            vol.Optional(
                CONF_MAX_CHARGE_MANUAL_POWER_W,
                default=values[CONF_MAX_CHARGE_MANUAL_POWER_W],
            ): str,
            # Netz: eine Netzleistungs-Entität mit Vorzeichen-Invertierung.
            vol.Optional(
                CONF_GRID_EXPORT_ENTITY,
                default=values[CONF_GRID_EXPORT_ENTITY],
            ): str,
            vol.Optional(
                CONF_INVERT_GRID_POWER_SIGN,
                default=values[CONF_INVERT_GRID_POWER_SIGN],
            ): BooleanSelector(),
        }

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
