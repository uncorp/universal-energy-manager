"""Config flow for UEM's safe, Shadow-only first installation."""

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
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
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


class UemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure UEM by selecting and confirming an existing E3DC RSCP entry."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize transient flow state."""
        self._e3dc_entry_id: str | None = None

    async def async_step_user(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Select an existing e3dc_rscp configuration entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        entries = self.hass.config_entries.async_entries(E3DC_RSCP_DOMAIN)
        if not entries:
            return self.async_abort(reason="e3dc_rscp_not_configured")

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
                title="UEM – Universal Energy Manager",
                data={
                    CONF_E3DC_CONFIG_ENTRY_ID: self._e3dc_entry_id,
                    CONF_E3DC_SOURCE_UNIQUE_ID: source_entry.unique_id,
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
