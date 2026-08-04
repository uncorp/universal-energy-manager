"""Regression tests for _build_entity_schema dead-code removal (Slice 6).

Requirements:
1. _build_entity_schema is dead code: it is not called by any flow step method.
2. The reconfigure step handles "no checkbox checked" correctly (loops back).
3. After removal, config_flow.py no longer defines _build_entity_schema.
4. Full test suite stays green after removal.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)

# =========================================================================== #
# TEST 1: _build_entity_schema is dead code (not called by any flow step)     #
# =========================================================================== #


class TestBuildEntitySchemaIsDeadCode:
    """Before removal: verify _build_entity_schema is unused by any async_step_*."""

    def test_no_flow_step_calls_build_entity_schema(self) -> None:
        """Inspect all async_step_* methods; none should call _build_entity_schema."""
        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN

        source_file = Path(inspect.getfile(UemConfigFlow))
        source_text = source_file.read_text(encoding="utf-8")

        # Find all async_step_* method definitions
        import re
        method_pattern = re.compile(
            r"async def (async_step_\w+)\s*\(",
            re.MULTILINE,
        )
        step_methods = method_pattern.findall(source_text)

        for method_name in step_methods:
            # Find the method body (from def to next def or end of class)
            method_regex = re.compile(
                rf"async def {method_name}\s*\([^)]*\)[^\n]*\n"
                r"(?:[ \t]+(?:async )?def [^\(]*\n"
                r"|(?:[ \t]+[a-zA-Z_]|)\n)*",
                re.MULTILINE,
            )
            match = method_regex.search(source_text)
            if match:
                method_body = match.group(0)
                assert "_build_entity_schema" not in method_body, (
                    f"async_step_{method_name} calls _build_entity_schema — "
                    "this method must not use the old helper; "
                    "it should use _build_full_schema instead."
                )


# =========================================================================== #
# TEST 2: _build_full_schema replaces _build_entity_schema                     #
# =========================================================================== #


class TestBuildFullSchemaReplacesEntitySchema:
    """After removal, _build_full_schema must serve as the single schema builder."""

    def test_build_full_schema_has_all_fields(self) -> None:
        """_build_full_schema returns 12 fields (10 entity fields + generators + batteries)."""
        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN

        schema_dict = flow._build_full_schema({})
        assert len(schema_dict) == 12, (
            f"Expected exactly 12 fields, got {len(schema_dict)}"
        )

    def test_build_full_schema_has_soc(self) -> None:
        from custom_components.universal_energy_manager.const import CONF_SOC_ENTITY

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN

        keys = set(str(k) for k in flow._build_full_schema({}).keys())
        assert CONF_SOC_ENTITY in keys


# =========================================================================== #
# TEST 3: Reconfigure step — no checkbox checked loops back                     #
# =========================================================================== #


def _make_flow_reconfigure(hass: MagicMock) -> UemConfigFlow:
    """Create a minimal flow for reconfigure testing."""
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


class TestReconfigureNoCheckbox:
    """Req 5: The reconfigure step must handle 'no checkbox checked' correctly."""

    def test_reconfigure_no_checkbox_loops_back(self) -> None:
        """When neither 'rescan_e3dc' nor 'edit_manual' is checked,
        the flow should show the form again (not abort, not create)."""
        import asyncio

        hass = MagicMock()
        flow = _make_flow_reconfigure(hass)

        # Set context to point to a non-existent entry — the reconfigure
        # step needs an entry. We'll provide one.
        from homeassistant import config_entries

        from custom_components.universal_energy_manager.const import DOMAIN as UEM_DOMAIN

        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=UEM_DOMAIN,
            title="UEM",
            data={},
            source="user",
            entry_id="uem-001",
            unique_id="uem:manual:test",
            state=config_entries.ConfigEntryState.LOADED,
        )
        _all_entries: dict[str, list] = {UEM_DOMAIN: [uem_entry]}

        def _async_entries2(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in _all_entries.values():
                    result.extend(entries)
                return result
            return _all_entries.get(domain, [])

        hass.config_entries.async_entries = MagicMock(side_effect=_async_entries2)
        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)

        flow.hass = hass
        flow.context = {"entry_id": "uem-001"}

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            flow.async_step_reconfigure({})
        )
        assert result["type"] == FlowResultType.FORM, (
            f"Expected FORM (loop back), got {result['type']}: {result}"
        )
        assert result["step_id"] == "reconfigure"


# =========================================================================== #
# TEST 4: After removal, _build_entity_schema attribute must not exist        #
# =========================================================================== #


class TestBuildEntitySchemaRemoved:
    """After the code removal slice, _build_entity_schema must be gone."""

    def test_method_removed(self) -> None:
        """UemConfigFlow must not have _build_entity_schema."""
        assert not hasattr(UemConfigFlow, "_build_entity_schema"), (
            "_build_entity_schema must be removed from UemConfigFlow"
        )

    def test_config_flow_source_has_no_build_entity_schema(self) -> None:
        """The source file must not contain the string '_build_entity_schema'."""
        source_file = Path(inspect.getfile(UemConfigFlow))
        source_text = source_file.read_text(encoding="utf-8")
        assert "_build_entity_schema" not in source_text, (
            "config_flow.py still contains _build_entity_schema references"
        )
