"""Regression test: field descriptions rendered via description_placeholders.

HA 2024.3.3 does NOT support data_description for config flows — it was added
in 2024.7+. For this pinned version, field explanations must be delivered through
the step's description text using description_placeholders.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel UND
eine kurze Erklärung direkt darunter.

This test verifies that:
1. strings.json step descriptions use {placeholder} tokens for field explanations
2. Config flow passes description_placeholders mapping those tokens to German text
3. The description_placeholders include explanations for ALL schema fields

This approach works natively in HA 2024.3.3's frontend.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_SOC_ENTITY,
)


def _load_strings() -> dict:
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


def _make_flow(hass: MagicMock) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list] = {E3DC_RSCP_DOMAIN: [], DOMAIN: []}

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all.values():
                result.extend(entries)
            return result
        return _all.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


def _mock_location(hass: MagicMock):
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TEST 1: strings.json step descriptions must use placeholder tokens          #
# =========================================================================== #


class TestStringsPlaceholderTokens:
    """Each step's description must contain {placeholder} tokens for field
    explanations so the frontend can render them."""

    def test_manual_mapping_description_has_placeholders(self):
        """manual_mapping description must reference field descriptions."""
        strings = _load_strings()
        desc = (
            strings.get("config", {})
            .get("step", {})
            .get("manual_mapping", {})
            .get("description", "")
        )
        # Must contain at least one {placeholder} token
        assert "{" in desc and "}" in desc, (
            "manual_mapping description must use {placeholder} tokens for "
            "field explanations (HA 2024.3.3 doesn't support data_description)"
        )

    def test_confirm_description_has_placeholders(self):
        """confirm description must reference field descriptions."""
        strings = _load_strings()
        desc = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("description", "")
        )
        assert "{" in desc and "}" in desc, (
            "confirm description must use {placeholder} tokens for "
            "field explanations"
        )


# =========================================================================== #
# TEST 2: Config flow passes description_placeholders for all schema fields   #
# =========================================================================== #

# The placeholder keys used by _build_description_placeholders (each schema
# key gets an _desc suffix).
_SCHEMA_PLACEHOLDER_KEYS = {
    "soc_entity_desc",
    "pv_power_entity_desc",
    "house_power_entity_desc",
    "battery_charge_entity_desc",
    "battery_capacity_entity_desc",
    "battery_manual_capacity_kwh_desc",
    "max_charge_power_entity_desc",
    "max_charge_manual_power_w_desc",
    "grid_export_entity_desc",
    "grid_power_sign_convention_desc",
}


class TestConfigFlowDescriptionPlaceholders:
    """Config flow must pass description_placeholders for ALL schema fields
    in manual_mapping and confirm steps."""

    def test_manual_mapping_passes_description_placeholders(self):
        """async_step_manual_mapping (form) must pass description_placeholders
        covering every field in _build_full_schema."""
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == "form"
        assert result["step_id"] == "manual_mapping"

        placeholders = result.get("description_placeholders")
        assert placeholders is not None, (
            "manual_mapping step must pass description_placeholders"
        )
        assert isinstance(placeholders, dict)

        # All schema placeholder keys must be present
        for key in _SCHEMA_PLACEHOLDER_KEYS:
            assert key in placeholders, (
                f"description_placeholders must include '{key}' for HA rendering"
            )

    def test_confirm_passes_description_placeholders(self):
        """async_step_confirm (form) must pass description_placeholders."""
        from homeassistant import config_entries

        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        # Mock e3dc_rscp entry so confirm step is reached
        e3dc_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=E3DC_RSCP_DOMAIN,
            title="E3DC RSCP",
            data={},
            source="user",
            entry_id="e3dc-001",
            unique_id="S10E-12345",
        )

        all_by_domain = {E3DC_RSCP_DOMAIN: [e3dc_entry], DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(
            side_effect=_async_entries
        )

        async def _go():
            r1 = await flow.async_step_user()
            # Confirm should show form (prefilled)
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )

        # Either confirm form or manual_mapping form
        assert result["type"] == "form"
        placeholders = result.get("description_placeholders")
        assert placeholders is not None, (
            f"{result['step_id']} step must pass description_placeholders"
        )
        assert isinstance(placeholders, dict)

        # Must include at least the core field placeholders
        for key in ("soc_entity_desc", "house_power_entity_desc", "grid_export_entity_desc"):
            assert key in placeholders, (
                f"description_placeholders must include '{key}'"
            )

    def test_description_placeholders_are_german(self):
        """All description placeholder values must be in German."""
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]

        for key, val in placeholders.items():
            assert val is not None and len(str(val).strip()) > 3, (
                f"description_placeholder '{key}' must have meaningful text"
            )
            val_lower = str(val).lower()
            # Must contain German keywords (not just English)
            assert any(
                kw in val_lower
                for kw in [
                    "entität", "leistung", "batterie", "netz", "haus", "verbrauch",
                    "ladestand", "kapazität", "vorzeichen", "bedeutet", "kann",
                    "soll", "messwert", "anlage", "positiv", "negativ",
                    "ein", "der", "die", "das",
                ]
            ), f"description_placeholder '{key}' must be in German, got: {val}"

    def test_house_power_placeholder_explains_negative_values(self):
        """house_power_entity placeholder must explain negative values."""
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]
        house_desc = str(placeholders.get("house_power_entity_desc", ""))

        assert (
            "negativ" in house_desc.lower()
            or "balkonkraftwerk" in house_desc.lower()
            or "produziert" in house_desc.lower()
        ), (
            f"house_power_entity description_placeholder must explain negative "
            f"values, got: {house_desc}"
        )

    def test_reconfigure_edit_passes_description_placeholders(self):
        """Reconfigure → edit flow must also pass description_placeholders."""
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_E3DC_CONFIG_ENTRY_ID,
            CONF_E3DC_SOURCE_UNIQUE_ID,
            CONF_MANUAL_ENTITIES,
            CONF_MAX_CHARGE_POWER_ENTITY,
        )

        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        uem_entry = MagicMock()
        uem_entry.entry_id = "uem-test"
        uem_entry.domain = DOMAIN
        uem_entry.version = 1
        uem_entry.minor_version = 1
        uem_entry.title = "UEM"
        uem_entry.data = {
            CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
            CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
            CONF_MANUAL_ENTITIES: False,
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
        }
        uem_entry.source = "user"
        uem_entry.unique_id = "uem:manual:test"
        uem_entry.state = MagicMock()

        all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(
            side_effect=_async_entries
        )
        flow.context = {"entry_id": uem_entry.entry_id}

        async def _go():
            r = await flow.async_step_reconfigure({"edit_manual": "True"})
            return r

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure_edit"

        placeholders = result.get("description_placeholders")
        assert placeholders is not None, "reconfigure_edit must pass description_placeholders"
        for key in _SCHEMA_PLACEHOLDER_KEYS:
            assert key in placeholders, (
                f"description_placeholders must include '{key}'"
            )
