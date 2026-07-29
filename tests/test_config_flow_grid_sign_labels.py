"""Regression test: grid sign convention labels use "bedeutet" not "=".

Requirement 2:
- Netzleistung deckt Import und Export über diese eine Entität ab.
- Direkt darunter gibt es eine verständliche Auswahl
  "Positiver Wert bedeutet Netzbezug" oder "Positiver Wert bedeutet Einspeisung".
- Keine zweite Netz-Entität und keine verstreute Import-/Export-Eingabe.

This test verifies that the vol.In options for the grid sign convention
selector use the exact German wording with "bedeutet" (not "=").
"""

from __future__ import annotations

from unittest.mock import MagicMock

import voluptuous as vol

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_GRID_POWER_SIGN_CONVENTION,
    SIGNED_CONVENTION_POS_DISCHARGE_IMPORT,
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
# TEST 1: Grid sign convention labels use "bedeutet"                          #
# =========================================================================== #


class TestGridSignConventionLabelWording:
    """The vol.In container must show 'Positiver Wert bedeutet Netzbezug'
    and 'Positiver Wert bedeutet Einspeisung' — not 'Positiver Wert = ...'."""

    def test_grid_sign_labels_use_bedeutet_not_equals(self) -> None:
        """Both grid sign convention options must contain the word 'bedeutet'."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        grid_sign_key = CONF_GRID_POWER_SIGN_CONVENTION
        validator = schema_dict.get(grid_sign_key)
        assert validator is not None, (
            f"{grid_sign_key} must be in the schema"
        )
        assert isinstance(validator, vol.In), (
            f"{grid_sign_key} validator must be vol.In"
        )
        for label in validator.container.values():
            assert "bedeutet" in label.lower(), (
                f"Grid sign convention label must contain 'bedeutet', "
                f"got: '{label}'"
            )

    def test_grid_sign_labels_no_equals(self) -> None:
        """No grid sign convention option should use '=' as separator."""
        flow = _make_flow()
        schema_dict = flow._build_full_schema({})
        grid_sign_key = CONF_GRID_POWER_SIGN_CONVENTION
        validator = schema_dict.get(grid_sign_key)
        assert validator is not None
        assert isinstance(validator, vol.In)
        for label in validator.container.values():
            assert "=" not in label, (
                f"Grid sign convention label must not use '=', "
                f"got: '{label}'"
            )

    def test_grid_sign_convention_default_is_netzbezug(self) -> None:
        """The default grid sign convention in _mapping_defaults must be
        'positive_is_discharging_import' (Netzbegzug) — the most common
        household expectation."""
        defaults = UemConfigFlow()._mapping_defaults()
        assert defaults[CONF_GRID_POWER_SIGN_CONVENTION] == (
            SIGNED_CONVENTION_POS_DISCHARGE_IMPORT
        ), (
            f"Default grid sign convention should be "
            f"'{SIGNED_CONVENTION_POS_DISCHARGE_IMPORT}' "
            f"(positive means Netzbezug), got: {defaults[CONF_GRID_POWER_SIGN_CONVENTION]}"
        )


# =========================================================================== #
# TEST 2: Grid sign convention in description_placeholder is "bedeutet"       #
# =========================================================================== #


class TestGridSignConventionDescPlaceholder:
    """The grid_power_sign_convention description_placeholder must also
    use correct 'bedeutet' wording."""

    def test_grid_sign_desc_placeholder_uses_bedeutet(self) -> None:
        """The grid_power_sign_convention_desc description placeholder
        must explain 'bedeutet' for positive values."""
        flow = _make_flow()
        placeholders = flow._build_description_placeholders()
        grid_desc = str(placeholders.get("grid_power_sign_convention_desc", ""))
        assert "bedeutet" in grid_desc.lower(), (
            f"grid_power_sign_convention_desc must explain 'bedeutet', "
            f"got: '{grid_desc}'"
        )
