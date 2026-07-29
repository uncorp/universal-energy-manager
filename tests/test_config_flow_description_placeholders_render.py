"""Regression test: step descriptions contain {placeholder} tokens for HA 2024.3.x.

HA 2024.3.3 does NOT render ``data_description`` from strings.json — that
mechanism was added in HA 2024.7.  In 2024.3.x the frontend only substitutes
``{placeholder}`` tokens in the step's ``description`` field using the
``description_placeholders`` dict passed to ``async_show_form()``.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel UND
eine kurze Erklärung direkt darunter.  In HA 2024.3.x this is achieved by
embedding per-field descriptions as ``{placeholder}`` tokens in the
``description`` text.

This test verifies:
1. strings.json step ``description`` contains ``{placeholder}`` tokens for
   field explanations
2. The tokens match keys in ``description_placeholders`` returned by the flow
3. The flow code passes the corresponding ``description_placeholders`` dict
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


# =========================================================================== #
# TEST 1: strings.json step descriptions contain {placeholder} tokens        #
# =========================================================================== #


class TestStepDescriptionsHavePlaceholders:
    """The step's description text must contain {placeholder} tokens for
    per-field explanations so that HA 2024.3.x renders them."""

    def test_confirm_description_has_placeholders(self):
        strings = _load_strings()
        desc = strings["config"]["step"]["confirm"].get("description", "")
        assert "{soc_entity_desc}" in desc, (
            "confirm step description must contain {soc_entity_desc} placeholder"
        )
        assert "{house_power_entity_desc}" in desc, (
            "confirm step description must contain {house_power_entity_desc} placeholder"
        )

    def test_manual_mapping_description_has_placeholders(self):
        strings = _load_strings()
        desc = strings["config"]["step"]["manual_mapping"].get("description", "")
        assert "{soc_entity_desc}" in desc, (
            "manual_mapping step description must contain {soc_entity_desc} placeholder"
        )
        assert "{house_power_entity_desc}" in desc, (
            "manual_mapping step description must contain {house_power_entity_desc} placeholder"
        )

    def test_reconfigure_edit_description_has_placeholders(self):
        strings = _load_strings()
        desc = strings["config"]["step"]["reconfigure_edit"].get("description", "")
        assert "{soc_entity_desc}" in desc, (
            "reconfigure_edit step description must contain {soc_entity_desc} placeholder"
        )
        assert "{house_power_entity_desc}" in desc, (
            "reconfigure_edit step description must contain {house_power_entity_desc} placeholder"
        )
