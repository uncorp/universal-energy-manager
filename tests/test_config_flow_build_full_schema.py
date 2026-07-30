"""Regression tests for _build_full_schema helper in config_flow.

Requirements:
- _build_full_schema returns exactly 10 fields (no more, no less)
- All 10 expected keys are present with correct defaults from _mapping_defaults
- All fields are truly optional (vol.Optional with no required constraint)
- All fields have NO vol.Length(min >= 1) — empty string is valid (Req 4)
- Pre-filled values override defaults correctly
- Grid sign convention defaults to False (Netzbezug)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import voluptuous as vol
from homeassistant.helpers.selector import BooleanSelector

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
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _make_flow() -> UemConfigFlow:
    """Create a minimal flow instance."""
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


def _get_schema_key(schema_dict: dict, key_name: str) -> vol.Optional:
    """Return the vol.Optional key object from the schema dict."""
    for k in schema_dict.keys():
        if str(k) == key_name:
            return k
    raise KeyError(f"Key {key_name!r} not found in schema")


# =========================================================================== #
# TEST 1: _build_full_schema returns exactly 10 fields                         #
# =========================================================================== #


class TestBuildFullSchemaFieldCount:
    """_build_full_schema must return exactly 10 fields."""

    def test_exact_field_count(self) -> None:
        """_build_full_schema({}) must return exactly 10 fields."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        assert len(schema_dict) == 10, (
            f"Expected exactly 10 fields, got {len(schema_dict)}: "
            f"{sorted(schema_dict.keys())}"
        )


# =========================================================================== #
# TEST 2: All expected fields present                                         #
# =========================================================================== #


class TestBuildFullSchemaFieldsPresent:
    """_build_full_schema must contain all 10 expected fields."""

    EXPECTED_FIELDS = frozenset({
        CONF_SOC_ENTITY,
        CONF_PV_POWER_ENTITY,
        CONF_HOUSE_POWER_ENTITY,
        CONF_BATTERY_CHARGE_ENTITY,
        CONF_BATTERY_CAPACITY_ENTITY,
        CONF_BATTERY_MANUAL_CAPACITY_KWH,
        CONF_MAX_CHARGE_POWER_ENTITY,
        CONF_MAX_CHARGE_MANUAL_POWER_W,
        CONF_GRID_EXPORT_ENTITY,
        CONF_INVERT_GRID_POWER_SIGN,
    })

    def test_all_expected_fields_present(self) -> None:
        """All 10 expected fields must be in the schema."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        schema_keys = {str(k) for k in schema_dict.keys()}
        missing = self.EXPECTED_FIELDS - schema_keys
        assert not missing, f"Missing fields: {missing}"
        extra = schema_keys - self.EXPECTED_FIELDS
        assert not extra, f"Unexpected extra fields: {extra}"


# =========================================================================== #
# TEST 3: All fields are optional (vol.Optional, not vol.Required)            #
# =========================================================================== #


class TestBuildFullSchemaAllOptional:
    """Every field in _build_full_schema must be wrapped in vol.Optional."""

    def test_all_keys_are_vol_optional(self) -> None:
        """All schema keys must be vol.Optional (not vol.Required)."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        for key in schema_dict.keys():
            assert isinstance(key, vol.Optional), (
                f"Key {key!r} should be vol.Optional, got {type(key).__name__}"
            )


# =========================================================================== #
# TEST 4: Grid sign convention defaults to DISCHARGE_IMPORT (Netzbezug)       #
# =========================================================================== #


class TestBuildFullSchemaDefaults:
    """Defaults must match _mapping_defaults output."""

    def _get_default_value(self, schema_dict: dict, key_name: str) -> str:
        """Extract the default value for a schema key."""
        vol_key = _get_schema_key(schema_dict, key_name)
        # The vol.Optional default is a callable (lambda) that returns the value
        if hasattr(vol_key, "default") and callable(vol_key.default):
            return vol_key.default()
        return getattr(vol_key, "default", None)

    def test_grid_sign_convention_default(self) -> None:
        """Grid sign convention must default to CHARGE_EXPORT."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        default_val = self._get_default_value(
            schema_dict, CONF_INVERT_GRID_POWER_SIGN
        )
        assert not default_val, (
            f"Expected {False!r}, "
            f"got {default_val!r}"
        )

    def test_defaults_empty_strings_for_entities(self) -> None:
        """Entity fields should default to empty strings."""
        flow = _make_flow()
        defaults = flow._mapping_defaults()
        for field in (
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_BATTERY_MANUAL_CAPACITY_KWH,
            CONF_MAX_CHARGE_POWER_ENTITY,
            CONF_MAX_CHARGE_MANUAL_POWER_W,
        ):
            assert defaults[field] == "", (
                f"{field} default should be empty string, got: {defaults[field]!r}"
            )


# =========================================================================== #
# TEST 5: Pre-filled values override defaults                                 #
# =========================================================================== #


class TestBuildFullSchemaPrefill:
    """Pre-filled values must override the defaults in _build_full_schema."""

    def _get_default_value(self, schema_dict: dict, key_name: str) -> str:
        """Extract the default value for a schema key."""
        vol_key = _get_schema_key(schema_dict, key_name)
        if hasattr(vol_key, "default") and callable(vol_key.default):
            return vol_key.default()
        return getattr(vol_key, "default", None)

    def test_prefill_overrides_soc(self) -> None:
        flow = _make_flow()
        prefill = {CONF_SOC_ENTITY: "sensor.prefilled_soc"}
        schema_dict = flow._build_full_schema(prefill)
        default_val = self._get_default_value(schema_dict, CONF_SOC_ENTITY)
        assert default_val == "sensor.prefilled_soc", (
            f"Expected 'sensor.prefilled_soc', got {default_val!r}"
        )

    def test_prefill_overrides_house_power(self) -> None:
        flow = _make_flow()
        prefill = {CONF_HOUSE_POWER_ENTITY: "sensor.my_house"}
        schema_dict = flow._build_full_schema(prefill)
        default_val = self._get_default_value(schema_dict, CONF_HOUSE_POWER_ENTITY)
        assert default_val == "sensor.my_house", (
            f"Expected 'sensor.my_house', got {default_val!r}"
        )

    def test_prefill_overrides_grid_sign(self) -> None:
        flow = _make_flow()
        prefill = {
            CONF_INVERT_GRID_POWER_SIGN:
                False
        }
        schema_dict = flow._build_full_schema(prefill)
        default_val = self._get_default_value(
            schema_dict, CONF_INVERT_GRID_POWER_SIGN
        )
        assert default_val is False, (
            f"Expected False, got {default_val!r}"
        )

    def test_prefill_overrides_battery_charge(self) -> None:
        flow = _make_flow()
        prefill = {CONF_BATTERY_CHARGE_ENTITY: "sensor.batt"}
        schema_dict = flow._build_full_schema(prefill)
        default_val = self._get_default_value(
            schema_dict, CONF_BATTERY_CHARGE_ENTITY
        )
        assert default_val == "sensor.batt", (
            f"Expected 'sensor.batt', got {default_val!r}"
        )


# =========================================================================== #
# TEST 6: No field has vol.Length(min >= 1) — Req 4: all truly optional        #
# =========================================================================== #


class TestBuildFullSchemaNoRequiredLength:
    """Req 4: No field may enforce vol.Length(min >= 1). Empty string must be
    accepted by the schema validator for every entity field."""

    def _get_validator(self, schema_dict: dict, key_name: str):
        """Return the validator (value) for a schema key."""
        vol_key = _get_schema_key(schema_dict, key_name)
        return schema_dict[vol_key]

    def _has_length_min_1(self, validator) -> bool:
        """Check if validator enforces a minimum length >= 1.

        Handles both direct vol.Length and vol.All containing vol.Length.
        """
        if isinstance(validator, vol.Length):
            min_val = getattr(validator, "min", None)
            if min_val is not None and min_val >= 1:
                return True
        if isinstance(validator, vol.All):
            for sub in validator.validators:
                if isinstance(sub, vol.Length):
                    min_val = getattr(sub, "min", None)
                    if min_val is not None and min_val >= 1:
                        return True
        return False

    def test_no_entity_field_requires_non_empty(self) -> None:
        """None of the entity fields should require a non-empty value."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})

        entity_fields = [
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_BATTERY_MANUAL_CAPACITY_KWH,
            CONF_MAX_CHARGE_POWER_ENTITY,
            CONF_MAX_CHARGE_MANUAL_POWER_W,
            CONF_GRID_EXPORT_ENTITY,
        ]
        for field in entity_fields:
            validator = self._get_validator(schema_dict, field)
            has_req = self._has_length_min_1(validator)
            assert not has_req, (
                f"{field} must NOT enforce vol.Length(min >= 1), "
                f"but validator is {validator}"
            )

    def test_grid_sign_convention_is_vol_in_not_length(self) -> None:
        """Grid sign convention should be vol.In, not vol.Length."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        validator = self._get_validator(
            schema_dict, CONF_INVERT_GRID_POWER_SIGN
        )
        assert isinstance(validator, BooleanSelector), (
            f"Grid sign convention should be BooleanSelector, got {type(validator)}"
        )
