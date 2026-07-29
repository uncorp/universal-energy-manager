"""Regression test: every schema field must have a matching data_description entry.

Requirement 5 (Req 5):
- Jede sichtbare Zeile braucht einen klaren deutschen Titel UND eine kurze Erklärung
  direkt darunter.
- HA 2024.3.3 does NOT support data_description — that was added in 2024.7+.
  For the pinned version, field explanations are delivered via description_placeholders
  in async_show_form(). However, strings.json still contains data_description blocks
  for future HA version compatibility.

This test verifies:
1. Every key in _build_full_schema() has a corresponding entry in
   strings.json data_description for each step that uses the schema
   (confirm, manual_mapping, reconfigure_edit).
2. The keys match exactly (no missing, no extra).
3. All descriptions are non-empty German text.
"""

from __future__ import annotations

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


def _schema_keys(flow: UemConfigFlow) -> set:
    """Return the top-level keys from the compiled schema dict."""
    return set(flow._build_full_schema({}).keys())


# =========================================================================== #
# TEST 1: Schema keys match strings.json data_description keys              #
# =========================================================================== #


class TestSchemaDataDescriptionConsistency:
    """Every schema field must have a corresponding data_description in strings.json."""

    def _dd_keys_from_step(self, step_id: str) -> set:
        """Return data_description keys for a given step in strings.json."""
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get(step_id, {})
            .get("data_description", {})
        )
        return set(dd.keys())

    def test_confirm_schema_matches_data_description(self) -> None:
        """confirm step: schema keys must match data_description keys exactly."""
        flow = _make_flow()
        schema_keys = _schema_keys(flow)
        dd_keys = self._dd_keys_from_step("confirm")
        missing = schema_keys - dd_keys
        extra = dd_keys - schema_keys
        assert not missing, (
            f"confirm/data_description missing keys from schema: {missing}"
        )
        assert not extra, (
            f"confirm/data_description extra keys not in schema: {extra}"
        )

    def test_manual_mapping_schema_matches_data_description(self) -> None:
        """manual_mapping step: schema keys must match data_description keys exactly."""
        flow = _make_flow()
        schema_keys = _schema_keys(flow)
        dd_keys = self._dd_keys_from_step("manual_mapping")
        missing = schema_keys - dd_keys
        extra = dd_keys - schema_keys
        assert not missing, (
            f"manual_mapping/data_description missing keys from schema: {missing}"
        )
        assert not extra, (
            f"manual_mapping/data_description extra keys not in schema: {extra}"
        )

    def test_reconfigure_edit_schema_matches_data_description(self) -> None:
        """reconfigure_edit step: schema keys must match data_description keys exactly."""
        flow = _make_flow()
        schema_keys = _schema_keys(flow)
        dd_keys = self._dd_keys_from_step("reconfigure_edit")
        missing = schema_keys - dd_keys
        extra = dd_keys - schema_keys
        assert not missing, (
            f"reconfigure_edit/data_description missing keys from schema: {missing}"
        )
        assert not extra, (
            f"reconfigure_edit/data_description extra keys not in schema: {extra}"
        )


# =========================================================================== #
# TEST 2: All data_description values are meaningful German text              #
# =========================================================================== #


class TestDataDescriptionValuesGerman:
    """Every data_description value must be non-empty German text."""

    def test_all_data_descriptions_non_empty(self) -> None:
        """No data_description entry should be empty or None."""
        strings = _load_strings()
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = (
                strings.get("config", {})
                .get("step", {})
                .get(step_id, {})
                .get("data_description", {})
            )
            for key, val in dd.items():
                assert val and len(str(val).strip()) > 3, (
                    f"{step_id}/data_description['{key}'] is empty or too short: "
                    f"{val!r}"
                )

    def test_data_descriptions_contain_german_words(self) -> None:
        """All data_description values should contain German words."""
        strings = _load_strings()
        german_keywords = [
            "entität", "leistung", "batterie", "netz", "haus", "verbrauch",
            "ladestand", "kapazität", "vorzeichen", "bedeutet", "kann",
            "soll", "messwert", "anlage", "positiv", "negativ", "ein",
            "der", "die", "das", "sensor", "zahl", "wert", "kwh", "watt",
        ]
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = (
                strings.get("config", {})
                .get("step", {})
                .get(step_id, {})
                .get("data_description", {})
            )
            for key, val in dd.items():
                val_lower = str(val).lower()
                assert any(kw in val_lower for kw in german_keywords), (
                    f"{step_id}/data_description['{key}'] doesn't appear to be "
                    f"German: {val!r}"
                )


# =========================================================================== #
# TEST 3: Schema keys match across all three steps                            #
# =========================================================================== #


class TestSchemaConsistencyAcrossSteps:
    """The schema returned by _build_full_schema must be identical
    for confirm, manual_mapping, and reconfigure_edit steps."""

    def test_same_schema_for_all_steps(self) -> None:
        """_build_full_schema returns the same dict regardless of step."""
        flow = _make_flow()
        schema = _schema_keys(flow)

        # The schema must be the same for all three steps
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd_keys = self._dd_keys_from_step(step_id)
            assert schema == dd_keys, (
                f"Step '{step_id}': schema keys {schema} don't match "
                f"data_description keys {dd_keys}"
            )

    def _dd_keys_from_step(self, step_id: str) -> set:
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get(step_id, {})
            .get("data_description", {})
        )
        return set(dd.keys())


# =========================================================================== #
# TEST 4: data_description keys match schema key naming convention            #
# =========================================================================== #


class TestDataDescriptionKeyNaming:
    """data_description keys use the config key name without CONF_ prefix."""

    def test_data_description_key_format(self) -> None:
        """data_description keys should use bare config key names (e.g.
        soc_entity, not CONF_SOC_ENTITY)."""
        flow = _make_flow()
        schema_keys = _schema_keys(flow)

        strings = _load_strings()
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = (
                strings.get("config", {})
                .get("step", {})
                .get(step_id, {})
                .get("data_description", {})
            )
            for key in dd:
                assert not key.startswith("CONF_"), (
                    f"{step_id}/data_description key '{key}' should not have CONF_ prefix"
                )
                # Each data_description key should map to a schema key
                # by matching the part after the last underscore (or whole key)
                assert key in schema_keys, (
                    f"{step_id}/data_description key '{key}' not in schema keys"
                )
