"""Regression test: grid sign selector changed from Select to BooleanSelector.

Requirement 2:
- Netzleistung deckt Import und Export über eine einzige Entität ab.
- Die Vorzeichen-Invertierung wird über einen BooleanSelector gesteuert.
- Default ist False (positiver Wert bedeutet Netzbezug).
- Keine zweite Netz-Entität und keine verstreute Import-/Export-Eingabe.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.helpers.selector import BooleanSelector

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_INVERT_GRID_POWER_SIGN,
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


class TestGridSignSelector:
    """Grid sign convention is now a BooleanSelector, not a Select."""

    def test_grid_sign_selector_is_boolean_selector(self) -> None:
        """The grid sign selector must be a BooleanSelector."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        validator = schema_dict.get(CONF_INVERT_GRID_POWER_SIGN)
        assert validator is not None
        assert isinstance(validator, BooleanSelector)

    def test_grid_sign_default_is_false(self) -> None:
        """Default invert_grid_power_sign is False (positive = Netzbezug)."""
        defaults = UemConfigFlow()._mapping_defaults()
        assert defaults[CONF_INVERT_GRID_POWER_SIGN] is False

    def test_grid_sign_convention_key_not_in_schema(self) -> None:
        """Old CONF_GRID_POWER_SIGN_CONVENTION must NOT be in the schema."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        assert CONF_GRID_POWER_SIGN_CONVENTION not in schema_dict


class TestGridSignDescriptionPlaceholder:
    """The new invert_grid_power_sign description placeholder exists."""

    def test_invert_grid_power_sign_desc_placeholder_exists(self) -> None:
        """The invert_grid_power_sign_desc placeholder must exist."""
        flow = _make_flow()
        placeholders = flow._build_description_placeholders()
        desc = str(placeholders.get("invert_grid_power_sign_desc", ""))
        assert "invert_grid_power_sign_desc" in placeholders
        assert len(desc) > 0

    def test_grid_export_entity_still_present(self) -> None:
        """CONF_GRID_EXPORT_ENTITY must still be in the schema."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        assert CONF_GRID_EXPORT_ENTITY in schema_dict
        assert schema_dict[CONF_GRID_EXPORT_ENTITY] is str
