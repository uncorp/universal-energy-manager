"""Config flow for UEM's universal, Shadow-only installation."""

from __future__ import annotations

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

_REQUIRED_FIELDS = (
    CONF_SOC_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
)

# Schema for manual entity mapping — all required fields
_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOC_ENTITY): str,
        vol.Required(CONF_PV_POWER_ENTITY): str,
        vol.Required(CONF_HOUSE_POWER_ENTITY): str,
        vol.Required(CONF_GRID_EXPORT_ENTITY): str,
        vol.Required(CONF_BATTERY_CHARGE_ENTITY): str,
        vol.Required(CONF_BATTERY_CAPACITY_ENTITY): str,
        vol.Required(CONF_MAX_CHARGE_POWER_ENTITY): str,
    }
)


def _entity_schema_with_defaults(
    defaults: dict[str, str | None],
) -> vol.Schema:
    """Build a form schema for required entity fields, prefilled with *defaults* where available."""
    return vol.Schema(
        {
            vol.Required(
                field,
                default=defaults.get(field),
            )
            if defaults.get(field)
            else vol.Required(field): str
            for field in _REQUIRED_FIELDS
        }
    )


class UemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure UEM by selecting and confirming an existing E3DC RSCP entry."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize transient flow state."""
        self._e3dc_entry_id: str | None = None
        self._manual_entity_data: dict[str, str] | None = None

    async def async_step_user(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Select an existing e3dc_rscp configuration entry or start manual mapping."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        entries = self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)
        if not entries:
            # No e3dc_rscp — fall through to manual mapping
            if user_input is not None:
                return await self.async_step_confirm_manual()
            return await self.async_step_manual()

        if len(entries) == 1:
            self._e3dc_entry_id = entries[0].entry_id
            return await self.async_step_confirm()

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

    async def async_step_manual(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Manual entity mapping — the universal default when no e3dc_rscp is available."""
        if user_input is not None:
            missing = [field for field in _REQUIRED_FIELDS if not user_input.get(field)]
            if missing:
                return self.async_show_form(
                    step_id="manual",
                    errors={"base": "missing_required_entities"},
                    description_placeholders={"missing": ", ".join(missing)},
                )
            self._manual_entity_data = user_input
            return await self.async_step_confirm_manual()

        return self.async_show_form(
            step_id="manual",
            description_placeholders={
                "info": (
                    "UEM is universal and does not require e3dc_rscp. "
                    "Enter the entity IDs from your energy system manually. "
                    "If e3dc_rscp is installed, you can also use the "
                    "\"Reconfigure\" action to re-discover entities."
                )
            },
            data_schema=_MANUAL_SCHEMA,
        )

    async def async_step_confirm_manual(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm and create entry after manual entity mapping."""
        if user_input is not None:
            entity_data = {**self._manual_entity_data} if self._manual_entity_data else {}
            # Collect all Forecast.Solar entries (unlimited — no fixed count)
            forecast_solar_entry_ids = [
                entry.entry_id
                for entry in self.hass.config_entries.async_entries(FORECAST_SOLAR_DOMAIN)
            ]
            return self.async_create_entry(
                title="UEM \u2013 Universal Energy Manager",
                data={
                    CONF_FORECAST_SOLAR_ENTRY_IDS: forecast_solar_entry_ids,
                    **entity_data,
                },
            )

        return self.async_show_form(
            step_id="confirm_manual",
            description_placeholders={
                "info": (
                    "You are creating a UEM entry using manually mapped entities. "
                    "These will be used for Shadow-mode planning only."
                )
            },
        )

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Show the detected entities and create a Shadow-only entry after confirmation."""
        if self._e3dc_entry_id is None:
            return await self.async_step_user()

        source_entry = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)
                if entry.entry_id == self._e3dc_entry_id
            ),
            None,
        )
        if source_entry is None:
            return self.async_abort(reason="e3dc_rscp_not_configured")

        forecast_solar_entry_ids = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(FORECAST_SOLAR_DOMAIN)
        ]
        discovered = self._discover_entities(self._e3dc_entry_id)
        entity_data = {
            CONF_SOC_ENTITY: discovered.soc,
            CONF_PV_POWER_ENTITY: discovered.pv_power,
            CONF_HOUSE_POWER_ENTITY: discovered.house_power,
            CONF_GRID_EXPORT_ENTITY: discovered.grid_export,
            CONF_BATTERY_CHARGE_ENTITY: discovered.battery_charge,
            CONF_BATTERY_CAPACITY_ENTITY: discovered.battery_capacity,
            CONF_MAX_CHARGE_POWER_ENTITY: discovered.max_charge_power,
        }
        missing = [field for field in _REQUIRED_FIELDS if not entity_data[field]]
        if missing:
            return self.async_show_form(
                step_id="confirm",
                errors={"base": "missing_required_entities"},
                description_placeholders={"missing": ", ".join(missing)},
            )

        if user_input is not None:
            await self.async_set_unique_id(
                uem_identity_from_source(source_entry.unique_id, source_entry.entry_id)
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="UEM \u2013 Universal Energy Manager",
                data={
                    CONF_E3DC_CONFIG_ENTRY_ID: self._e3dc_entry_id,
                    CONF_E3DC_SOURCE_UNIQUE_ID: source_entry.unique_id,
                    CONF_FORECAST_SOLAR_ENTRY_IDS: forecast_solar_entry_ids,
                    **entity_data,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "detected": str(sum(value is not None for value in entity_data.values()))
            },
        )

    def _discover_entities(self, config_entry_id: str):
        """Read only source entities belonging to the selected e3dc_rscp entry."""
        registry = er.async_get(self.hass)
        unique_ids = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(registry, config_entry_id)
            if entry.domain == "sensor" and entry.unique_id is not None
        }
        return discover_e3dc_entities(source_by_key_from_unique_ids(unique_ids))


class UemOptionsFlow(config_entries.OptionsFlow):
    """Reconfigure UEM entry — re-discover entities without overwriting manual mappings."""

    VERSION = 1

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize with the existing config entry."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Reconfigure existing entry — re-discover entities as suggestions."""
        # Read existing entity mappings (user's manual choices — preserved)
        existing_data = dict(self.config_entry.data)
        existing_e3dc_entry_id = existing_data.get(CONF_E3DC_CONFIG_ENTRY_ID)

        # Try to discover from e3dc_rscp if an entry_id is stored;
        # only fill gaps — never overwrite existing values.
        if existing_e3dc_entry_id:
            discovered = self._discover_entities(existing_e3dc_entry_id)
            for field in _REQUIRED_FIELDS:
                if not existing_data.get(field):
                    value = getattr(discovered, field.replace("_entity", ""), None)
                    if value:
                        existing_data[field] = value

        # Collect all Forecast.Solar entries (unlimited)
        forecast_solar_entry_ids = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(FORECAST_SOLAR_DOMAIN)
        ]
        existing_data[CONF_FORECAST_SOLAR_ENTRY_IDS] = forecast_solar_entry_ids

        if user_input is not None:
            # User confirmed — update the entry with merged data
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            return self.async_create_entry(data={})

        # Build schema with existing values as defaults (not forced)
        defaults = {field: existing_data.get(field) for field in _REQUIRED_FIELDS}
        schema = _entity_schema_with_defaults(defaults)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "info": (
                    "Re-discovered entities are shown as suggestions. "
                    "Your existing mappings are preserved unless changed."
                )
            },
        )

    def _discover_entities(self, config_entry_id: str):
        """Read only source entities belonging to the selected e3dc_rscp entry."""
        registry = er.async_get(self.hass)
        unique_ids = {
            entry.unique_id: entry.entity_id
            for entry in er.async_entries_for_config_entry(registry, config_entry_id)
            if entry.domain == "sensor" and entry.unique_id is not None
        }
        return discover_e3dc_entities(source_by_key_from_unique_ids(unique_ids))
