"""Regression test: dead power-mode constants fully removed from config_flow.

After the simplified schema (v0.1.8-rc.2), the following constants are no longer
used by the config flow and must NOT appear in any schema, defaults, or imports
within config_flow.py:

  - CONF_BATTERY_POWER_MODE
  - CONF_BATTERY_POWER_SIGN_CONVENTION
  - CONF_BATTERY_DISCHARGE_ENTITY
  - CONF_GRID_POWER_MODE
  - CONF_GRID_IMPORT_ENTITY

Additionally, _ENT_MAP_LOOKUP must NOT contain CONF_BATTERY_DISCHARGE_ENTITY.

These constants may still exist in const.py for backward compatibility with
existing entries, but the config_flow module must not reference them.
"""

from __future__ import annotations

import ast
from pathlib import Path

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _make_flow() -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = __import__("unittest.mock").mock.MagicMock()
    flow.hass.config_entries.async_entries.side_effect = lambda domain=None: {
        E3DC_RSCP_DOMAIN: [],
        DOMAIN: [],
    }.get(domain, [])
    flow.hass.config_entries.async_entry_for_domain_unique_id.return_value = None
    flow.context = {}
    flow.handler = DOMAIN
    return flow


# =========================================================================== #
# TEST 1: config_flow.py AST must not import dead constants                    #
# =========================================================================== #


class TestConfigFlowAstNoDeadImports:
    """The config_flow.py source must not import dead constants."""

    def _get_imports(self) -> list[str]:
        cfg_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "config_flow.py"
        )
        source = cfg_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "const":
                for alias in node.names:
                    imports.append(alias.name)
        return imports

    def test_no_battery_power_mode_import(self):
        """CONF_BATTERY_POWER_MODE must not be imported in config_flow.py."""
        imports = self._get_imports()
        assert "CONF_BATTERY_POWER_MODE" not in imports

    def test_no_battery_power_sign_convention_import(self):
        """CONF_BATTERY_POWER_SIGN_CONVENTION must not be imported in config_flow.py."""
        imports = self._get_imports()
        assert "CONF_BATTERY_POWER_SIGN_CONVENTION" not in imports

    def test_no_battery_discharge_entity_import(self):
        """CONF_BATTERY_DISCHARGE_ENTITY must not be imported in config_flow.py."""
        imports = self._get_imports()
        assert "CONF_BATTERY_DISCHARGE_ENTITY" not in imports

    def test_no_grid_power_mode_import(self):
        """CONF_GRID_POWER_MODE must not be imported in config_flow.py."""
        imports = self._get_imports()
        assert "CONF_GRID_POWER_MODE" not in imports

    def test_no_grid_import_entity_import(self):
        """CONF_GRID_IMPORT_ENTITY must not be imported in config_flow.py."""
        imports = self._get_imports()
        assert "CONF_GRID_IMPORT_ENTITY" not in imports


# =========================================================================== #
# TEST 2: _mapping_defaults must not contain dead keys                         #
# =========================================================================== #


class TestMappingDefaultsNoDeadKeys:
    """_mapping_defaults() returns only the fields used in the simplified schema."""

    def test_no_battery_discharge_in_defaults(self):
        flow = _make_flow()
        defaults = flow._mapping_defaults()
        assert "battery_discharge_entity" not in defaults

    def test_no_battery_power_mode_in_defaults(self):
        flow = _make_flow()
        defaults = flow._mapping_defaults()
        assert "battery_power_mode" not in defaults

    def test_no_grid_power_mode_in_defaults(self):
        flow = _make_flow()
        defaults = flow._mapping_defaults()
        assert "grid_power_mode" not in defaults


# =========================================================================== #
# TEST 3: _ENT_MAP_LOOKUP must not reference dead constants                    #
# =========================================================================== #


class TestEntMapLookupNoDeadKeys:
    """_ENT_MAP_LOOKUP must only contain mappings for fields in the simplified schema."""

    def _get_ent_map_lookup(self) -> dict:
        from custom_components.universal_energy_manager.const import _ENT_MAP_LOOKUP
        return dict(_ENT_MAP_LOOKUP)

    def test_no_battery_discharge_in_ent_map_lookup(self):
        lookup = self._get_ent_map_lookup()
        assert "battery_discharge_entity" not in lookup

    def test_only_expected_keys_in_ent_map_lookup(self):
        """_ENT_MAP_LOOKUP should contain exactly 7 keys used in rescan."""
        lookup = self._get_ent_map_lookup()
        expected_keys = {
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_MAX_CHARGE_POWER_ENTITY,
        }
        assert set(lookup.keys()) == expected_keys


# =========================================================================== #
# TEST 4: Source code text must not reference dead constants in config_flow    #
# =========================================================================== #


class TestConfigFlowSourceNoDeadReferences:
    """The config_flow.py source must not contain any references to dead constants."""

    def _get_source(self) -> str:
        cfg_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "config_flow.py"
        )
        return cfg_path.read_text(encoding="utf-8")

    def test_no_battery_discharge_entity_string(self):
        source = self._get_source()
        assert "battery_discharge_entity" not in source

    def test_no_battery_power_mode_string(self):
        source = self._get_source()
        assert "battery_power_mode" not in source

    def test_no_grid_power_mode_string(self):
        source = self._get_source()
        assert "grid_power_mode" not in source

    def test_no_grid_import_entity_string(self):
        source = self._get_source()
        assert "grid_import_entity" not in source

    def test_no_battery_power_sign_convention_string(self):
        source = self._get_source()
        assert "battery_power_sign_convention" not in source

    def test_no_separate_or_signed_mode_strings(self):
        source = self._get_source()
        assert "BATTERY_POWER_MODE_SEPARATE" not in source
        assert "BATTERY_POWER_MODE_SIGNED" not in source
        assert "GRID_POWER_MODE_SEPARATE" not in source
        assert "GRID_POWER_MODE_SIGNED" not in source
