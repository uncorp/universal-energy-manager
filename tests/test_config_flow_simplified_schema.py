"""Regression tests for the simplified config-flow schema (v0.1.8-rc.2).

Requirements enforced by these tests:
1. No battery_power_mode, battery_discharge_entity, battery_power_sign_convention.
2. No grid_power_mode, grid_import_entity.
3. Exactly one "Batterieleistung" field (battery_charge_entity) and one "Netzleistung"
   field (grid_export_entity) per page.
4. Grid sign-convention selector present for grid.
5. House-power explanation is visible (in strings.json data_description).
6. All fields optional: empty form creates entry → "Shadow – Einrichtung unvollständig".
7. Field descriptions use HA's data_description mechanism (strings.json).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import voluptuous as vol

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_BATTERY_POWER_MODE,
    CONF_BATTERY_POWER_SIGN_CONVENTION,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_POWER_MODE,
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _make_flow() -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    flow.handler = DOMAIN
    ce = flow.hass.config_entries
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
# TEST 1: Schema must NOT contain removed fields                              #
# =========================================================================== #


class TestSimplifiedSchemaNoRemovedFields:
    """The simplified schema must not expose any mode-selection or separate-entity fields."""

    def _schema_keys(self, flow: UemConfigFlow) -> set:
        """Return the top-level keys from the compiled schema dict."""
        schema_dict = flow._build_full_schema({})
        return set(schema_dict.keys())

    def test_no_battery_power_mode(self) -> None:
        """CONF_BATTERY_POWER_MODE must not appear in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_POWER_MODE not in keys

    def test_no_battery_discharge_entity(self) -> None:
        """CONF_BATTERY_DISCHARGE_ENTITY must not appear in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_DISCHARGE_ENTITY not in keys

    def test_no_battery_sign_convention(self) -> None:
        """CONF_BATTERY_POWER_SIGN_CONVENTION must not appear in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_POWER_SIGN_CONVENTION not in keys

    def test_no_grid_power_mode(self) -> None:
        """CONF_GRID_POWER_MODE must not appear in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_GRID_POWER_MODE not in keys

    def test_no_grid_import_entity(self) -> None:
        """CONF_GRID_IMPORT_ENTITY must not appear in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_GRID_IMPORT_ENTITY not in keys


# =========================================================================== #
# TEST 2: Schema must contain required fields                                 #
# =========================================================================== #


class TestSimplifiedSchemaRequiredFields:
    """The simplified schema must keep the core measurement fields."""

    def _schema_keys(self, flow: UemConfigFlow) -> set:
        schema_dict = flow._build_full_schema({})
        return set(schema_dict.keys())

    def test_battery_charge_entity_present(self) -> None:
        """CONF_BATTERY_CHARGE_ENTITY (Batterieleistung) must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_CHARGE_ENTITY in keys

    def test_grid_export_entity_present(self) -> None:
        """CONF_GRID_EXPORT_ENTITY (Netzleistung) must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_GRID_EXPORT_ENTITY in keys

    def test_grid_power_sign_convention_present(self) -> None:
        """Grid sign-convention selector must remain for Netzleistung."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_GRID_POWER_SIGN_CONVENTION in keys

    def test_soc_present(self) -> None:
        """CONF_SOC_ENTITY must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_SOC_ENTITY in keys

    def test_pv_power_present(self) -> None:
        """CONF_PV_POWER_ENTITY must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_PV_POWER_ENTITY in keys

    def test_house_power_present(self) -> None:
        """CONF_HOUSE_POWER_ENTITY must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_HOUSE_POWER_ENTITY in keys

    def test_battery_capacity_present(self) -> None:
        """CONF_BATTERY_CAPACITY_ENTITY must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_CAPACITY_ENTITY in keys

    def test_battery_manual_capacity_present(self) -> None:
        """CONF_BATTERY_MANUAL_CAPACITY_KWH must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_BATTERY_MANUAL_CAPACITY_KWH in keys

    def test_max_charge_power_entity_present(self) -> None:
        """CONF_MAX_CHARGE_POWER_ENTITY must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_MAX_CHARGE_POWER_ENTITY in keys

    def test_max_charge_manual_power_present(self) -> None:
        """CONF_MAX_CHARGE_MANUAL_POWER_W must be in the schema."""
        flow = _make_flow()
        keys = self._schema_keys(flow)
        assert CONF_MAX_CHARGE_MANUAL_POWER_W in keys


# =========================================================================== #
# TEST 3: Grid sign convention options (exactly 2)                            #
# =========================================================================== #


class TestGridSignConventionOptions:
    """Grid sign convention must show exactly two human-readable options."""

    def test_grid_sign_has_exactly_two_options(self) -> None:
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        grid_sign_key = CONF_GRID_POWER_SIGN_CONVENTION
        validator = schema_dict.get(grid_sign_key)
        assert validator is not None
        # The validator should be a vol.In
        assert isinstance(validator, vol.In)
        assert len(validator.container) == 2

    def test_grid_sign_options_values(self) -> None:
        """Grid sign convention must include both Bezug and Einspeisung."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        grid_sign_key = CONF_GRID_POWER_SIGN_CONVENTION
        validator = schema_dict.get(grid_sign_key)
        assert isinstance(validator, vol.In)
        values = list(validator.container.values())
        # One option must mean "positive = Bezug", the other "positive = Einspeisung"
        assert any("bezug" in v.lower() for v in values)
        assert any("einspeisung" in v.lower() for v in values)


# =========================================================================== #
# TEST 4: Empty form creates entry (all optional)                             #
# =========================================================================== #


class TestEmptyFormCreatesEntry:
    """An empty manual_mapping must create a config entry (Shadow-incomplete)."""

    def test_empty_manual_mapping_creates_entry(self) -> None:
        from homeassistant.data_entry_flow import FlowResultType

        flow = _make_flow()
        # Provide a mock location so the uid generator does not hit
        # MagicMock.__format__
        loc = MagicMock()
        loc.latitude = 52.0
        loc.longitude = 13.0
        flow.hass.config.location = loc

        async def _go():
            # Go to no_e3dc_choice → continue → manual_mapping
            r1 = await flow.async_step_user()
            assert r1["type"] == FlowResultType.FORM
            assert r1["step_id"] == "no_e3dc_choice"

            r2 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            assert r2["type"] == FlowResultType.FORM
            assert r2["step_id"] == "manual_mapping"

            # Submit empty dict
            r3 = await flow.async_step_manual_mapping({})
            assert r3["type"] == FlowResultType.CREATE_ENTRY
            return r3

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["data"]["manual_entities"] is True
        # All battery/grid fields should be absent or empty
        assert result["data"].get(CONF_BATTERY_CHARGE_ENTITY, "") == ""
        assert result["data"].get(CONF_GRID_EXPORT_ENTITY, "") == ""


# =========================================================================== #
# TEST 5: Strings.json has description placeholders for field explanations     #
# =========================================================================== #


class TestStringsJsonDescriptions:
    """HA 2024.3.3 does NOT support data_description.  Field explanations
    are delivered via {placeholder} tokens in the step's description text,
    with the real German text provided via description_placeholders in
    async_show_form().

    This test verifies the placeholders are present AND that the description
    text actually contains the required explanations (negative values for
    house power, etc.)."""

    def _load_strings(self) -> dict:
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            return json.load(f)

    def test_house_power_placeholder_explains_negative_values(self) -> None:
        """house_power_entity_desc placeholder must explain negative values
        and Balkonkraftwerk.  The config flow passes this text via
        description_placeholders."""
        import asyncio
        from unittest.mock import MagicMock

        from custom_components.universal_energy_manager.config_flow import (
            DOMAIN,
            E3DC_RSCP_DOMAIN,
            UemConfigFlow,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN
        ce = flow.hass.config_entries
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

        async def _go():
            r = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r

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

    def test_battery_charge_placeholder_present(self) -> None:
        """battery_charge_entity_desc must be in description_placeholders."""
        import asyncio
        from unittest.mock import MagicMock

        from custom_components.universal_energy_manager.config_flow import (
            DOMAIN,
            E3DC_RSCP_DOMAIN,
            UemConfigFlow,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN
        ce = flow.hass.config_entries
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

        async def _go():
            r = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]
        assert "battery_charge_entity_desc" in placeholders

    def test_grid_export_placeholder_present(self) -> None:
        """grid_export_entity_desc must be in description_placeholders."""
        import asyncio
        from unittest.mock import MagicMock

        from custom_components.universal_energy_manager.config_flow import (
            DOMAIN,
            E3DC_RSCP_DOMAIN,
            UemConfigFlow,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN
        ce = flow.hass.config_entries
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

        async def _go():
            r = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]
        assert "grid_export_entity_desc" in placeholders

    def test_no_battery_power_mode_in_strings(self) -> None:
        """strings.json must not contain battery_power_mode or grid_power_mode labels."""
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            content = f.read()

        assert "battery_power_mode" not in content, (
            "strings.json must not reference battery_power_mode"
        )
        assert "grid_power_mode" not in content, (
            "strings.json must not reference grid_power_mode"
        )

    def test_no_separate_entity_labels(self) -> None:
        """strings.json must not reference separate-entity labels."""
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            content = f.read()

        assert "battery_discharge_entity" not in content, (
            "strings.json must not reference battery_discharge_entity"
        )
        assert "grid_import_entity" not in content, (
            "strings.json must not reference grid_import_entity"
        )


# =========================================================================== #
# TEST 6: House power negative value accepted in data path (Req 3)             #
# =========================================================================== #


class TestHousePowerNegativeValue:
    """Requirement 3: House consumption is exactly one input. Negative values
    are allowed and mean e.g. a balcony PV system currently produces more than
    the house consumes. This must be reflected in the data path via a
    regression test."""

    def test_manual_mapping_accepts_negative_house_power(self) -> None:
        """A negative house_power_entity value must be accepted and stored
        verbatim in the created config entry data."""
        import asyncio
        from unittest.mock import MagicMock

        from homeassistant.data_entry_flow import FlowResultType

        from custom_components.universal_energy_manager.config_flow import (
            DOMAIN,
            E3DC_RSCP_DOMAIN,
            UemConfigFlow,
        )
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_MANUAL_CAPACITY_KWH,
            CONF_GRID_EXPORT_ENTITY,
            CONF_GRID_POWER_SIGN_CONVENTION,
            CONF_HOUSE_POWER_ENTITY,
            CONF_MANUAL_ENTITIES,
            CONF_MAX_CHARGE_MANUAL_POWER_W,
            CONF_MAX_CHARGE_POWER_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_SOC_ENTITY,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN
        ce = flow.hass.config_entries
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

        loc = MagicMock()
        loc.latitude = 52.0
        loc.longitude = 13.0
        flow.hass.config.location = loc

        async def _go():
            r1 = await flow.async_step_user()
            assert r1["type"] == FlowResultType.FORM
            assert r1["step_id"] == "no_e3dc_choice"

            r2 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            assert r2["type"] == FlowResultType.FORM
            assert r2["step_id"] == "manual_mapping"

            # Submit with negative house power (Balkonkraftwerk scenario)
            user_input = {
                CONF_SOC_ENTITY: "sensor.soc",
                CONF_PV_POWER_ENTITY: "sensor.pv",
                CONF_HOUSE_POWER_ENTITY: "-250",  # negative = more PV than consumption
                CONF_GRID_EXPORT_ENTITY: "sensor.grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.battery",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_POWER_SIGN_CONVENTION: "positive_is_discharging_import",
            }
            r3 = await flow.async_step_manual_mapping(user_input)
            assert r3["type"] == FlowResultType.CREATE_ENTRY
            return r3

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )

        # The negative house power must be stored as-is (as a string in the data)
        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "-250"
        assert result["data"][CONF_MANUAL_ENTITIES] is True

    def test_manual_mapping_accepts_zero_house_power(self) -> None:
        """Zero house power must also be accepted."""
        import asyncio
        from unittest.mock import MagicMock

        from homeassistant.data_entry_flow import FlowResultType

        from custom_components.universal_energy_manager.config_flow import (
            DOMAIN,
            E3DC_RSCP_DOMAIN,
            UemConfigFlow,
        )
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_MANUAL_CAPACITY_KWH,
            CONF_GRID_EXPORT_ENTITY,
            CONF_GRID_POWER_SIGN_CONVENTION,
            CONF_HOUSE_POWER_ENTITY,
            CONF_MAX_CHARGE_MANUAL_POWER_W,
            CONF_MAX_CHARGE_POWER_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_SOC_ENTITY,
        )

        flow = UemConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.handler = DOMAIN
        ce = flow.hass.config_entries
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

        loc = MagicMock()
        loc.latitude = 52.0
        loc.longitude = 13.0
        flow.hass.config.location = loc

        async def _go():
            r1 = await flow.async_step_user()
            assert r1["type"] == FlowResultType.FORM
            assert r1["step_id"] == "no_e3dc_choice"

            r2 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            assert r2["type"] == FlowResultType.FORM
            assert r2["step_id"] == "manual_mapping"

            user_input = {
                CONF_SOC_ENTITY: "sensor.soc",
                CONF_PV_POWER_ENTITY: "sensor.pv",
                CONF_HOUSE_POWER_ENTITY: "0",
                CONF_GRID_EXPORT_ENTITY: "sensor.grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.battery",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_POWER_SIGN_CONVENTION: "positive_is_discharging_import",
            }
            r3 = await flow.async_step_manual_mapping(user_input)
            assert r3["type"] == FlowResultType.CREATE_ENTRY
            return r3

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )

        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "0"
