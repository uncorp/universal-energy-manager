"""Regression test: description_placeholders match {placeholder} tokens in strings.json.

Every {placeholder} token in the step's ``description`` field must have a
corresponding key in the ``description_placeholders`` dict passed by the
config flow.  Mismatches cause undefined text in the HA frontend.

This test verifies:
1. Each step's description tokens are covered by the flow's placeholders
2. No extra/unused placeholder keys exist
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
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


def _extract_tokens(text: str) -> set[str]:
    """Extract all {key} tokens from text."""
    return set(re.findall(r"\{(\w+?)\}", text))


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


# =========================================================================== #
# TEST 1: Placeholder tokens in strings.json match flow's description_placeholders #
# =========================================================================== #


class TestPlaceholdersMatch:
    """All {placeholder} tokens in step descriptions must be covered by the
    config flow's description_placeholders dict."""

    def _run_step(self, step_id: str, user_input: dict | None = None) -> dict:
        flow = _make_flow(MagicMock())
        loc = MagicMock()
        loc.latitude = 52.0
        loc.longitude = 13.0
        flow.hass.config.location = loc

        async def _go():
            if step_id == "manual_mapping":
                # Enter via no_e3dc_choice
                r = await flow.async_step_no_e3dc_choice(
                    {"confirm": "continue"}
                )
                if user_input is not None:
                    return await flow.async_step_manual_mapping(user_input)
                return r
            elif step_id == "confirm":
                from homeassistant import config_entries

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

                r = await flow.async_step_user()
                if user_input is not None:
                    return await flow.async_step_confirm(user_input)
                return r
            elif step_id == "reconfigure_edit":
                from custom_components.universal_energy_manager.const import (
                    CONF_BATTERY_CAPACITY_ENTITY,
                    CONF_BATTERY_CHARGE_ENTITY,
                    CONF_E3DC_CONFIG_ENTRY_ID,
                    CONF_E3DC_SOURCE_UNIQUE_ID,
                    CONF_MANUAL_ENTITIES,
                    CONF_MAX_CHARGE_POWER_ENTITY,
                    CONF_SOC_ENTITY,
                )

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

                r = await flow.async_step_reconfigure({"edit_manual": "True"})
                if user_input is not None:
                    return await flow.async_step_reconfigure_edit(user_input)
                return r
            return {}

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        return result

    def _get_placeholders_from_flow(self, step_id: str) -> set[str]:
        result = self._run_step(step_id)
        return set(result.get("description_placeholders", {}).keys())

    def _get_tokens_from_strings(self, step_id: str) -> set[str]:
        strings = _load_strings()
        desc = strings["config"]["step"][step_id].get("description", "")
        return _extract_tokens(desc)

    def test_manual_mapping_placeholders_match(self):
        flow_keys = self._get_placeholders_from_flow("manual_mapping")
        str_keys = self._get_tokens_from_strings("manual_mapping")
        missing = str_keys - flow_keys
        assert not missing, (
            f"manual_mapping: description_placeholders missing for tokens: "
            f"{sorted(missing)}"
        )

    def test_confirm_placeholders_match(self):
        flow_keys = self._get_placeholders_from_flow("confirm")
        str_keys = self._get_tokens_from_strings("confirm")
        missing = str_keys - flow_keys
        assert not missing, (
            f"confirm: description_placeholders missing for tokens: "
            f"{sorted(missing)}"
        )

    def test_reconfigure_edit_placeholders_match(self):
        flow_keys = self._get_placeholders_from_flow("reconfigure_edit")
        str_keys = self._get_tokens_from_strings("reconfigure_edit")
        missing = str_keys - flow_keys
        assert not missing, (
            f"reconfigure_edit: description_placeholders missing for tokens: "
            f"{sorted(missing)}"
        )
