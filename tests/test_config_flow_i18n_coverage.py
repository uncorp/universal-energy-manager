"""i18n coverage tests: English base in strings.json + complete German in de.json.

Verifies that:
1. strings.json (English base) has all required keys populated with English text.
2. translations/de.json (German) has the same key structure with German text.
3. Both files share the exact same key topology (step IDs, data keys, etc.).
4. No German text leaks into strings.json base.
5. No English text remains untranslated in de.json.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "universal_energy_manager"
)


def _load_json(filename: str) -> dict:
    with open(BASE_PATH / filename, encoding="utf-8") as f:
        return json.load(f)


def _extract_leaf_values(obj: dict, prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict into {path: value} where value is always a string."""
    result = {}
    for key, val in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            result.update(_extract_leaf_values(val, path))
        else:
            result[path] = str(val)
    return result


# =========================================================================== #
# TEST 1: English base — all step fields present                             #
# =========================================================================== #


class TestEnglishBaseCompleteness:
    """strings.json must be a complete English base."""

    _REQUIRED_STEPS = frozenset(
        {"user", "confirm", "no_e3dc_choice", "manual_mapping",
         "reconfigure", "reconfigure_edit"}
    )
    _REQUIRED_FIELDS = frozenset(
        {"title", "description", "data", "data_description"}
    )
    _STEP_DATA_FIELDS = frozenset({
        "soc_entity", "pv_power_entity", "house_power_entity",
        "battery_charge_entity", "battery_capacity_entity",
        "battery_manual_capacity_kwh", "max_charge_power_entity",
        "max_charge_manual_power_w", "grid_export_entity",
        "invert_grid_power_sign",
    })

    _ENGLISH_KEYWORDS = frozenset({
        "entity", "power", "battery", "grid", "house", "consumption",
        "charge", "capacity", "sign", "negative", "positive", "can",
        "sensor", "system", "optional", "fixed", "value", "report",
        "current", "number", "watt", "kwh", "import", "export",
        "enable", "expected", "install", "means", "produce",
        "incomplete", "setup", "confirm", "select", "choose",
        "adapter", "integration", "change", "edit", "save", "reload",
        "already", "first", "later", "cancel", "safe", "shadow",
        "control", "command", "assignment", "measurement",
    })

    def test_strings_json_has_required_steps(self) -> None:
        strings = _load_json("strings.json")
        steps = strings.get("config", {}).get("step", {})
        missing = self._REQUIRED_STEPS - set(steps.keys())
        assert not missing, f"strings.json step keys missing: {missing}"

    def test_strings_json_step_titles_present(self) -> None:
        strings = _load_json("strings.json")
        for step_id in self._REQUIRED_STEPS:
            title = (
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("title", "")
            )
            assert len(title.strip()) > 2, (
                f"strings.json '{step_id}' title must be meaningful: {title!r}"
            )

    def test_strings_json_step_descriptions_present(self) -> None:
        strings = _load_json("strings.json")
        for step_id in self._REQUIRED_STEPS:
            desc = (
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("description", "")
            )
            assert len(desc.strip()) > 2, (
                f"strings.json '{step_id}' description must be present: {desc!r}"
            )

    def test_strings_json_data_keys_cover_all_fields(self) -> None:
        """All mapping steps must have the same data keys."""
        strings = _load_json("strings.json")
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            data_keys = set(
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("data", {}).keys()
            )
            missing = self._STEP_DATA_FIELDS - data_keys
            assert not missing, (
                f"strings.json '{step_id}/data' missing fields: {missing}"
            )

    def test_strings_json_data_description_keys_cover_all_fields(self) -> None:
        """All mapping steps must have data_description for every field."""
        strings = _load_json("strings.json")
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd_keys = set(
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("data_description", {}).keys()
            )
            missing = self._STEP_DATA_FIELDS - dd_keys
            assert not missing, (
                f"strings.json '{step_id}/data_description' missing fields: {missing}"
            )

    def test_strings_json_abort_keys_present(self) -> None:
        aborts = _load_json("strings.json").get("config", {}).get("abort", {})
        required = {"single_instance_allowed", "e3dc_rscp_not_configured",
                    "e3dc_rscp_optional_cancel", "already_configured",
                    "not_configured", "reconfigure_successful"}
        missing = required - set(aborts.keys())
        assert not missing, f"strings.json abort keys missing: {missing}"

    def test_strings_json_error_keys_present(self) -> None:
        errors = _load_json("strings.json").get("config", {}).get("error", {})
        assert "missing_required_entities" in errors, (
            "strings.json error/missing_required_entities must be present"
        )

    def test_strings_json_values_are_english(self) -> None:
        """All string values in strings.json must be English (base locale)."""
        strings = _load_json("strings.json")
        leaves = _extract_leaf_values(strings)
        for path, val in leaves.items():
            val_lower = val.lower()
            # Skip paths that might contain placeholder tokens like {var}
            if not any(kw in val_lower for kw in self._ENGLISH_KEYWORDS):
                # Allow placeholder-only content
                if val.strip() and "{" not in val and "}" not in val:
                    assert False, (
                        f"strings.json '{path}' = {val!r} does not appear to "
                        f"be English text"
                    )


# =========================================================================== #
# TEST 2: German translation — same key topology                              #
# =========================================================================== #


class TestGermanTranslationTopology:
    """translations/de.json must mirror strings.json key structure exactly."""

    def test_de_json_has_same_steps(self) -> None:
        de = _load_json("translations/de.json")
        strings = _load_json("strings.json")
        de_steps = set(de.get("config", {}).get("step", {}).keys())
        en_steps = set(strings.get("config", {}).get("step", {}).keys())
        missing = en_steps - de_steps
        assert not missing, f"de.json missing steps: {missing}"
        extra = de_steps - en_steps
        assert not extra, f"de.json has extra steps: {extra}"

    def test_de_json_has_same_data_keys_per_step(self) -> None:
        de = _load_json("translations/de.json")
        strings = _load_json("strings.json")
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            de_data = set(
                de.get("config", {}).get("step", {}).get(step_id, {})
                .get("data", {}).keys()
            )
            en_data = set(
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("data", {}).keys()
            )
            assert de_data == en_data, (
                f"de.json/{step_id}/data keys differ: "
                f"extra={en_data - de_data}, missing={de_data - en_data}"
            )

    def test_de_json_has_same_data_description_keys_per_step(self) -> None:
        de = _load_json("translations/de.json")
        strings = _load_json("strings.json")
        for step_id in ("confirm", "manual_mapping", "reconfigure_edit"):
            de_dd = set(
                de.get("config", {}).get("step", {}).get(step_id, {})
                .get("data_description", {}).keys()
            )
            en_dd = set(
                strings.get("config", {}).get("step", {}).get(step_id, {})
                .get("data_description", {}).keys()
            )
            assert de_dd == en_dd, (
                f"de.json/{step_id}/data_description keys differ: "
                f"extra={en_dd - de_dd}, missing={de_dd - en_dd}"
            )

    def test_de_json_has_same_aborts(self) -> None:
        de = _load_json("translations/de.json")
        strings = _load_json("strings.json")
        de_aborts = set(de.get("config", {}).get("abort", {}).keys())
        en_aborts = set(strings.get("config", {}).get("abort", {}).keys())
        assert de_aborts == en_aborts, (
            f"abort keys differ: extra={en_aborts - de_aborts}, "
            f"missing={de_aborts - en_aborts}"
        )

    def test_de_json_has_same_errors(self) -> None:
        de = _load_json("translations/de.json")
        strings = _load_json("strings.json")
        de_errors = set(de.get("config", {}).get("error", {}).keys())
        en_errors = set(strings.get("config", {}).get("error", {}).keys())
        assert de_errors == en_errors, (
            f"error keys differ: extra={en_errors - de_errors}, "
            f"missing={de_errors - en_errors}"
        )


# =========================================================================== #
# TEST 3: German translation — all values are German                          #
# =========================================================================== #


class TestGermanTranslationValues:
    """translations/de.json values must be German, not English."""

    _GERMAN_KEYWORDS = frozenset({
        "entität", "leistung", "batterie", "netz", "haus", "verbrauch",
        "ladestand", "kapazität", "vorzeichen", "bedeutet", "kann",
        "soll", "anlage", "fest", "wahl", "bedeutet", "kann",
        "positiv", "negativ", "sensor", "zahl", "wert", "kwh", "watt",
        "optional", "aktivieren", "erwartet", "einrichtung",
        "schatten", "schattenmodus", "steuerung", "steuern",
        "komplett", "unvollständig", "einspeisung", "bezug",
        "einfügen", "entladen", "laden",
    })

    def test_de_values_contain_german_words(self) -> None:
        de = _load_json("translations/de.json")
        leaves = _extract_leaf_values(de)
        for path, val in leaves.items():
            val_lower = val.lower()
            if len(val.strip()) < 3:
                continue
            if "{" in val and "}" in val:
                # Placeholder-only values are OK (they reference English)
                continue
            assert any(kw in val_lower for kw in self._GERMAN_KEYWORDS), (
                f"de.json '{path}' = {val!r} does not appear to be German"
            )


# =========================================================================== #
# TEST 4: English base — no German text leaks                                 #
# =========================================================================== #


class TestEnglishBaseNoGerman:
    """strings.json must not contain German text."""

    _GERMAN_KEYWORDS = frozenset({
        "entität", "leistung", "batterie", "netz", "haus", "verbrauch",
        "ladestand", "kapazität", "vorzeichen", "bedeutet", "kann",
        "soll", "anlage", "fest", "wahl", "positiv", "negativ",
        "sensor", "zahl", "wert", "kwh", "watt", "aktivieren",
        "erwartet", "einrichtung", "schatten", "steuerung",
        "einspeisung", "bezug", "entladen", "laden",
    })

    def test_strings_json_no_german_words(self) -> None:
        strings = _load_json("strings.json")
        leaves = _extract_leaf_values(strings)
        for path, val in leaves.items():
            val_lower = val.lower()
            if len(val.strip()) < 3:
                continue
            if "{" in val and "}" in val:
                continue
            assert not any(kw in val_lower for kw in self._GERMAN_KEYWORDS), (
                f"strings.json '{path}' = {val!r} contains German text"
            )
