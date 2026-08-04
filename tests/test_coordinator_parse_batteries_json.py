"""TDD tests for UEM Task B: Multi-Quelle/Multi-Akku — Battery JSON parsing.

Slice 3: Verifying _parse_batteries_json edge cases.

This parser is shared between _sum_generators_power_w and
_sum_additional_battery_capacity, so correctness here is critical.
"""

from __future__ import annotations

import json

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_NAME,
    CONF_BATTERY_SOC_ENTITY,
)
from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator


class TestParseBatteriesJson:
    """Tests for UemShadowCoordinator._parse_batteries_json()."""

    def _make_coordinator(self, entry_data: dict) -> UemShadowCoordinator:
        """Create a minimal coordinator for testing."""
        from unittest.mock import MagicMock

        hass = MagicMock()
        entry = MagicMock()
        entry.data = entry_data
        entry.entry_id = "test-entry"
        entry.async_on_unload = MagicMock()
        coordinator = UemShadowCoordinator(hass, entry)
        coordinator.hass = hass
        return coordinator

    def test_none_returns_empty_list(self) -> None:
        """None input → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json(None) == []

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json("") == []

    def test_non_string_returns_empty_list(self) -> None:
        """Non-string input (e.g. a list directly) → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json(["not", "json"]) == []

    def test_malformed_json_returns_empty_list(self) -> None:
        """Malformed JSON string → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json("{invalid") == []

    def test_json_string_not_list_returns_empty_list(self) -> None:
        """Valid JSON but not a list → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json('{"key": "value"}') == []

    def test_valid_empty_list(self) -> None:
        """'[]' → empty list."""
        coord = self._make_coordinator({})
        assert coord._parse_batteries_json("[]") == []

    def test_valid_single_battery(self) -> None:
        """Single battery dict → list with one dict."""
        coord = self._make_coordinator({})
        bat = {
            CONF_BATTERY_NAME: "Wall-Power",
            CONF_BATTERY_SOC_ENTITY: "sensor.wallpower_soc",
            CONF_BATTERY_CAPACITY_KWH: "10",
            CONF_BATTERY_CHARGE_POWER_ENTITY: "sensor.wallpower_charge",
            CONF_BATTERY_DISCHARGE_POWER_ENTITY: "sensor.wallpower_discharge",
        }
        result = coord._parse_batteries_json(json.dumps([bat], ensure_ascii=False))
        assert len(result) == 1
        assert result[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert result[0][CONF_BATTERY_CAPACITY_KWH] == "10"

    def test_valid_multiple_batteries(self) -> None:
        """Multiple batteries → list with all dicts."""
        coord = self._make_coordinator({})
        bats = [
            {
                CONF_BATTERY_NAME: "Wall-Power",
                CONF_BATTERY_SOC_ENTITY: "sensor.wallpower_soc",
                CONF_BATTERY_CAPACITY_KWH: "10",
                CONF_BATTERY_CHARGE_POWER_ENTITY: "",
                CONF_BATTERY_DISCHARGE_POWER_ENTITY: "",
            },
            {
                CONF_BATTERY_NAME: "Second-Battery",
                CONF_BATTERY_SOC_ENTITY: "sensor.second_soc",
                CONF_BATTERY_CAPACITY_KWH: "5",
                CONF_BATTERY_CHARGE_POWER_ENTITY: "",
                CONF_BATTERY_DISCHARGE_POWER_ENTITY: "",
            },
        ]
        result = coord._parse_batteries_json(json.dumps(bats, ensure_ascii=False))
        assert len(result) == 2
        assert result[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert result[1][CONF_BATTERY_NAME] == "Second-Battery"

    def test_list_with_non_dict_items_skipped(self) -> None:
        """List containing non-dict items returns only dicts."""
        coord = self._make_coordinator({})
        data = [
            {"battery_name": "Valid"},
            "not a dict",
            42,
            None,
            {"battery_name": "Also Valid"},
        ]
        result = coord._parse_batteries_json(json.dumps(data, ensure_ascii=False))
        assert len(result) == 2
        assert result[0]["battery_name"] == "Valid"
        assert result[1]["battery_name"] == "Also Valid"

    def test_unicode_preserved(self) -> None:
        """Unicode characters in battery names are preserved."""
        coord = self._make_coordinator({})
        bat = {
            CONF_BATTERY_NAME: "Wall-Power (Außen)",
            CONF_BATTERY_SOC_ENTITY: "sensor.wallpower_soc",
            CONF_BATTERY_CAPACITY_KWH: "10",
            CONF_BATTERY_CHARGE_POWER_ENTITY: "",
            CONF_BATTERY_DISCHARGE_POWER_ENTITY: "",
        }
        result = coord._parse_batteries_json(json.dumps([bat], ensure_ascii=False))
        assert len(result) == 1
        assert result[0][CONF_BATTERY_NAME] == "Wall-Power (Außen)"
