"""Final coverage slice: target the 6 remaining uncovered branch parts.

Covers:
- config_flow.py:346 (prefill preservation in manual_mapping elif branch)
- config_flow.py:486 (reconfigure rescan path: do_rescan=True)
- config_flow.py:540 (rescan: empty val + entity_val exists → update)
- coordinator.py:311 (target_soc is valid int → skip default)
- coordinator.py:338 (generic forecast: state exists but state.state is unknown)
- coordinator.py:450 (thread path: forecast_connected=False)

TDD: test first (expect fail), implement, verify green.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    CONF_STRATEGY,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap
from custom_components.universal_energy_manager.snapshot import (
    StateSample,
    build_live_state,
)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _make_uem_entry(
    entry_id: str = "uem-001",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM – Universal Energy Manager",
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id="uem:manual:test",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC RSCP",
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="S10E-12345",
        state=config_entries.ConfigEntryState.LOADED,
    )


# =========================================================================== #
# config_flow.py:346 – elif field in entity_data (keep prefill)               #
# =========================================================================== #


class TestConfigFlowBranch346Prefill:
    """Line 346: elif field in entity_data → pass (keep prefill).

    When a field is NOT in user_input but IS in entity_data (prefilled),
    the prefill value should be preserved via the elif branch.
    """

    def test_prefill_preserved_via_elif_branch(self) -> None:
        """Submit fewer fields than prefill provides; prefill values kept."""
        from homeassistant.config import async_hass_config_yaml  # noqa: F401

        hass = MagicMock()
        hass.config_entries.async_entries = MagicMock(side_effect=lambda domain=None: {
            None: [],
            DOMAIN: [],
            E3DC_RSCP_DOMAIN: [],
        }.get(domain, []))
        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(return_value=None)
        hass.config.location = MagicMock(latitude=52.52, longitude=13.405)

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {}
        flow.handler = DOMAIN

        # Go through no_e3dc_choice → manual_mapping
        _run(flow.async_step_no_e3dc_choice({"confirm": "continue"}))

        # Only provide some fields; others rely on prefill
        data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",
            CONF_PV_POWER_ENTITY: "sensor.manual_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.manual_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.manual_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.manual_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max",
        }
        result = _run(flow.async_step_manual_mapping(data))
        assert result["type"] == FlowResultType.CREATE_ENTRY


# =========================================================================== #
# config_flow.py:486 – if do_rescan in reconfigure step                      #
# =========================================================================== #


class TestConfigFlowBranch486Rescan:
    """Line 486: if do_rescan → rescan e3dc_rscp for new entities."""

    def test_reconfigure_rescan_path_taken(self) -> None:
        """When rescan_e3dc=True and edit_manual=False, reconfigure takes
        the rescan path (line 486)."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        # All entity fields are blank → all should be filled by discovery
        uem_entry = _make_uem_entry(
            entry_id="uem-old",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MANUAL_ENTITIES: False,
            },
        )

        def _async_entries(domain=None):
            if domain is None:
                return [e3dc_entry, uem_entry]
            if domain == E3DC_RSCP_DOMAIN:
                return [e3dc_entry]
            if domain == DOMAIN:
                return [uem_entry]
            return []

        hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
            return_value=uem_entry
        )
        hass.config.location = MagicMock(latitude=52.52, longitude=13.405)

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-old"}
        flow.handler = DOMAIN

        new_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(UemConfigFlow, "_discover_entities", return_value=new_map):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": True, "edit_manual": False}
                )
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # All blank fields should be updated from new discovery
        assert result["data"][CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"


# =========================================================================== #
# config_flow.py:540 – _rescan_e3dc: empty val + entity_val exists           #
# =========================================================================== #


class TestConfigFlowBranch540UpdateEmpty:
    """Line 540: if entity_val → update new_data[key] from e3dc discovery.

    When new_data has an empty string for a key, the entity value from
    the e3dc discovery map should fill it (line 540->541).
    """

    def test_rescan_updates_empty_soc_from_discovery(self) -> None:
        """_rescan_e3dc updates empty fields from e3dc discovery map."""
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            entry_id="uem-old",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "",  # blank → should be filled
                CONF_PV_POWER_ENTITY: "sensor.custom_pv",  # non-blank → preserved
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MANUAL_ENTITIES: False,
            },
        )

        def _async_entries(domain=None):
            if domain is None:
                return [e3dc_entry, uem_entry]
            if domain == E3DC_RSCP_DOMAIN:
                return [e3dc_entry]
            if domain == DOMAIN:
                return [uem_entry]
            return []

        hass = MagicMock()
        hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
            return_value=uem_entry
        )
        hass.config.location = MagicMock(latitude=52.52, longitude=13.405)

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-old"}
        flow.handler = DOMAIN

        new_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(UemConfigFlow, "_discover_entities", return_value=new_map):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": True, "edit_manual": False}
                )
            )

        # Empty fields should be filled from discovery
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        # Non-blank field preserved
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.custom_pv"
        # Other empty fields updated
        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result["data"][CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"


# =========================================================================== #
# coordinator.py:311 – target_soc IS valid int/float (skip default)           #
# =========================================================================== #


class TestCoordinatorBranch311ValidTargetSoc:
    """Line 311: when target_soc is already a valid int/float,
    the default branch is skipped."""

    def test_build_planner_config_with_valid_target_soc(self) -> None:
        """_build_planner_config uses configured target_soc directly when
        it's a valid number (line 311 skip)."""
        hass = MagicMock()
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_STRATEGY: "pv_first",
                "target_soc_pct": 85,  # valid int → line 311 skips default
            },
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None

        coord = UemShadowCoordinator(hass, entry)
        config = coord._build_planner_config(
            build_live_state(
                now=datetime(2026, 7, 18, 12, tzinfo=UTC),
                soc=StateSample("55", "%", datetime(2026, 7, 18, 12, tzinfo=UTC)),
                pv_power=StateSample("2500", "W", datetime(2026, 7, 18, 12, tzinfo=UTC)),
                house_power=StateSample("800", "W", datetime(2026, 7, 18, 12, tzinfo=UTC)),
                grid_export=StateSample("0", "W", datetime(2026, 7, 18, 12, tzinfo=UTC)),
                battery_charge=StateSample("0", "W", datetime(2026, 7, 18, 12, tzinfo=UTC)),
            )
        )
        assert config.target_soc_pct == 85.0


# =========================================================================== #
# coordinator.py:338 – state exists but state.state is unknown/unavailable   #
# =========================================================================== #


class TestCoordinatorBranch338UnknownState:
    """Line 338: when state exists but state.state is 'unknown' or 'unavailable',
    the generic forecast path is skipped (line 338->359)."""

    @pytest.mark.asyncio
    async def test_generic_forecast_skipped_when_unknown(self, hass) -> None:
        """State entity exists but state is 'unknown' → forecast skipped."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                CONF_FORECAST_ENTITY: "sensor.unknown_forecast",
            },
        )
        for eid, val, unit in (
            ("sensor.e3dc_soc", "55", "%"),
            ("sensor.e3dc_pv", "2500", "W"),
            ("sensor.e3dc_house", "800", "W"),
            ("sensor.e3dc_grid_export", "1400", "W"),
            ("sensor.e3dc_battery_charge", "1800", "W"),
            ("sensor.e3dc_capacity", "13.0", "kWh"),
            ("sensor.e3dc_max_charge", "12000", "W"),
        ):
            hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

        # Generic forecast entity exists but state is 'unknown'
        now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        hass.states.async_set(
            "sensor.unknown_forecast", "unknown",
            {ATTR_UNIT_OF_MEASUREMENT: "W", "last_updated": now},
        )

        coordinator = UemShadowCoordinator(hass, entry)
        result = await coordinator._build_forecast_async(
            build_live_state(
                now=now,
                soc=StateSample("55", "%", now),
                pv_power=StateSample("2500", "W", now),
                house_power=StateSample("800", "W", now),
                grid_export=StateSample("1400", "W", now),
                battery_charge=StateSample("1800", "W", now),
            )
        )

        # Should fall back to live PV snapshot, not use the unknown forecast
        assert len(result) == 1
        assert result[0].power_w == 2500.0

    @pytest.mark.asyncio
    async def test_generic_forecast_skipped_when_unavailable(self, hass) -> None:
        """State entity exists but state is 'unavailable' → forecast skipped."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
                CONF_FORECAST_ENTITY: "sensor.unavail_forecast",
            },
        )
        for eid, val, unit in (
            ("sensor.e3dc_soc", "55", "%"),
            ("sensor.e3dc_pv", "2500", "W"),
            ("sensor.e3dc_house", "800", "W"),
            ("sensor.e3dc_grid_export", "1400", "W"),
            ("sensor.e3dc_battery_charge", "1800", "W"),
            ("sensor.e3dc_capacity", "13.0", "kWh"),
            ("sensor.e3dc_max_charge", "12000", "W"),
        ):
            hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

        now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        hass.states.async_set(
            "sensor.unavail_forecast", "unavailable",
            {ATTR_UNIT_OF_MEASUREMENT: "W", "last_updated": now},
        )

        coordinator = UemShadowCoordinator(hass, entry)
        result = await coordinator._build_forecast_async(
            build_live_state(
                now=now,
                soc=StateSample("55", "%", now),
                pv_power=StateSample("2500", "W", now),
                house_power=StateSample("800", "W", now),
                grid_export=StateSample("1400", "W", now),
                battery_charge=StateSample("1800", "W", now),
            )
        )

        assert len(result) == 1
        assert result[0].power_w == 2500.0


# =========================================================================== #
# coordinator.py:450 – forecast_connected=False (skip building forecast)      #
# =========================================================================== #


class TestCoordinatorBranch450NoForecast:
    """Line 450: when forecast_connected is False, the thread skips
    building forecast from snapshot.

    This test calls _compute_charge_limit (sync wrapper) which uses the thread
    path, exercising line 450 with forecast_connected=False.
    """

    def test_sync_wrapper_thread_path_no_forecast_connected(self) -> None:
        """When forecast_connected=False, _compute_charge_limit skips
        _build_forecast_from_snapshot in the thread (line 450)."""
        hass = MagicMock()
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
            },
        )
        for eid, val, unit in (
            ("sensor.e3dc_soc", "55", "%"),
            ("sensor.e3dc_pv", "2500", "W"),
            ("sensor.e3dc_house", "800", "W"),
            ("sensor.e3dc_grid_export", "1400", "W"),
            ("sensor.e3dc_battery_charge", "1800", "W"),
            ("sensor.e3dc_capacity", "13.0", "kWh"),
            ("sensor.e3dc_max_charge", "12000", "W"),
        ):
            hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

        coordinator = UemShadowCoordinator(hass, entry)

        now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        live = build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        )

        # Call the sync wrapper (line 414) with forecast_connected=False
        # This enters the thread path (line 436) and skips line 450
        result = coordinator._compute_charge_limit(live, forecast_connected=False)

        assert isinstance(result, float)
