"""Config-flow integration tests against a real Home Assistant test instance."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
)


@pytest.mark.asyncio
async def test_user_flow_aborts_without_e3dc_rscp(
    hass, enable_custom_integrations
) -> None:
    """A UEM entry cannot be created without its read-only E3DC source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "e3dc_rscp_not_configured"


@pytest.mark.asyncio
async def test_user_flow_prefills_e3dc_rscp_entities_and_creates_shadow_entry(
    hass, enable_custom_integrations
) -> None:
    """The real flow must create only a Shadow entry from registry discovery."""
    source_entry = MockConfigEntry(
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC S10",
        unique_id="S10E-12345",
    )
    source_entry.add_to_hass(hass)
    forecast_entries = [
        MockConfigEntry(domain="forecast_solar", title="Hauptdach"),
        MockConfigEntry(domain="forecast_solar", title="Balkon"),
    ]
    for forecast_entry in forecast_entries:
        forecast_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for source_key in (
        "soc",
        "solar-production",
        "house-consumption",
        "grid-production",
        "battery-charge",
        "system-battery-installed-capacity",
        "system-battery-charge-max",
    ):
        registry.async_get_or_create(
            "sensor",
            E3DC_RSCP_DOMAIN,
            f"S10E-12345_{source_key}",
            config_entry=source_entry,
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"detected": "7"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UEM – Universal Energy Manager"
    assert result["data"]["e3dc_source_unique_id"] == "S10E-12345"
    assert result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS] == [
        entry.entry_id for entry in forecast_entries
    ]
