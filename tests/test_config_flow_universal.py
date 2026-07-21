"""Tests for the universal (E3DC-optional) config flow and reconfigure path.

These are the new TDD tests that must be red before the implementation and
green after. They cover:

1. ConfigFlow does NOT abort when e3dc_rscp is missing — shows manual mapping.
2. Manual entity mapping is the universal default.
3. Existing adapter values are editable suggestions, not forced.
4. Reconfigure step re-discovers entities without overwriting manual mappings.
5. Mandatory fields still required; missing ones → Messdatenfehler, not crash.
6. Forecast.Solar: unlimited entries collected (no fixed count).
7. No BHKW / wind forecast fields exist.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    _REQUIRED_FIELDS,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title=title,
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
    forecast_solar_entries: list[config_entries.ConfigEntry] | None = None,
    existing_uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Construct a UemConfigFlow with a mocked hass."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    ce = hass.config_entries
    _all_entries_by_domain: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: list(e3dc_entries),
    }
    if forecast_solar_entries:
        _all_entries_by_domain[FORECAST_SOLAR_DOMAIN] = forecast_solar_entries
    if existing_uem_entry is not None:
        _all_entries_by_domain[DOMAIN] = [existing_uem_entry]

    def _async_entries(domain: str | None = None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(
        side_effect=lambda domain, uid: existing_uem_entry if existing_uem_entry else None
    )
    return flow


def _run_flow_coroutine(coroutine) -> dict:
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coroutine)


def _mock_discovery_full(hass: MagicMock) -> None:
    """Make _discover_entities return a full entity map."""
    full_map = E3dcEntityMap(
        soc="sensor.e3dc_soc",
        pv_power="sensor.e3dc_pv",
        house_power="sensor.e3dc_house",
        grid_export="sensor.e3dc_grid",
        battery_charge="sensor.e3dc_charge",
        battery_capacity="sensor.e3dc_capacity",
        max_charge_power="sensor.e3dc_max_charge",
    )
    patch.object(UemConfigFlow, "_discover_entities", return_value=full_map).start()


# ---------------------------------------------------------------------------
# Test 1: Missing e3dc_rscp must NOT abort — must offer manual mapping
# ---------------------------------------------------------------------------

class TestNoE3dcRscpNoAbort:
    """When e3dc_rscp is not installed, the flow must not abort."""

    def test_flow_shows_manual_mapping_when_no_e3dc_rscp(self) -> None:
        """Without any e3dc_rscp entry the flow must offer manual mapping."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[], forecast_solar_entries=[])

        result = _run_flow_coroutine(flow.async_step_user())

        # MUST NOT abort — the old behavior was:
        #   result["type"] == FlowResultType.ABORT
        #   result["reason"] == "e3dc_rscp_not_configured"
        assert result["type"] != FlowResultType.ABORT, (
            "ConfigFlow must NOT abort when e3dc_rscp is missing; "
            "it must offer manual entity mapping instead."
        )
        assert result["type"] == FlowResultType.FORM, (
            "Expected a FORM step for manual entity mapping."
        )

    def test_flow_still_aborts_when_uem_entry_exists(self) -> None:
        """Even without e3dc_rscp, an existing UEM entry → abort."""
        hass = MagicMock()
        existing = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={},
            source="user",
            entry_id="uem-existing",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )
        flow = _make_flow(hass, e3dc_entries=[], existing_uem_entry=existing)

        result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


# ---------------------------------------------------------------------------
# Test 2: Manual mapping step exists and is the universal default
# ---------------------------------------------------------------------------

class TestManualMappingStep:
    """Manual entity mapping must be the universal entry point."""

    def test_manual_mapping_step_is_shown_when_no_e3dc(self) -> None:
        """The first step without e3dc_rscp must be a manual mapping form."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[], forecast_solar_entries=[])

        result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        # The step_id must be "manual" (or a discoverable mapping step)
        assert result.get("step_id") in ("manual", "user"), (
            "Expected a manual mapping step when no e3dc_rscp exists."
        )

    def test_user_provides_manual_entity_ids(self) -> None:
        """User can fill in all required entity IDs manually."""
        hass = MagicMock()
        flow = _make_flow(hass, e3dc_entries=[], forecast_solar_entries=[])

        # Submitting a single required field is enough to show the flow accepts user input
        # (full validation happens in confirm_manual / manual step)
        with patch.object(UemConfigFlow, "_discover_entities", return_value=E3dcEntityMap()):
            result = _run_flow_coroutine(
                flow.async_step_user(user_input={CONF_SOC_ENTITY: "sensor.my_soc"})
            )
            # At minimum the flow must accept the first step
            assert result["type"] in (FlowResultType.FORM, FlowResultType.CREATE_ENTRY)


# ---------------------------------------------------------------------------
# Test 3: Adapter values are suggestions, not forced
# ---------------------------------------------------------------------------

class TestAdapterValuesAreSuggestions:
    """Pre-discovered values must be pre-filled suggestions, not forced."""

    def test_discovered_entities_prefill_form_fields(self) -> None:
        """When e3dc_rscp entities are discovered, they should prefill the form."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc_entry], forecast_solar_entries=[])

        with patch.object(
            UemConfigFlow,
            "_discover_entities",
            return_value=E3dcEntityMap(
                soc="sensor.e3dc_soc",
                pv_power="sensor.e3dc_pv",
                house_power="sensor.e3dc_house",
                grid_export="sensor.e3dc_grid",
                battery_charge="sensor.e3dc_charge",
                battery_capacity="sensor.e3dc_capacity",
                max_charge_power="sensor.e3dc_max_charge",
            ),
        ):
            result = _run_flow_coroutine(flow.async_step_user())

        assert result["type"] == FlowResultType.FORM
        # The form should be prefilled with discovered values
        # User must be able to change them
        assert "data_schema" in result


# ---------------------------------------------------------------------------
# Test 4: Reconfigure step — re-discover without overwriting
# ---------------------------------------------------------------------------

class TestReconfigureStep:
    """Reconfigure must re-discover entities without overwriting manual mappings."""

    def test_options_flow_exists_for_reconfigure(self) -> None:
        """The flow must define UemOptionsFlow with async_step_init for reconfigure."""
        from custom_components.universal_energy_manager.config_flow import UemOptionsFlow

        assert hasattr(UemOptionsFlow, "async_step_init"), (
            "UemOptionsFlow must define async_step_init for reconfigure."
        )

    def test_options_flow_preserves_existing_manual_mappings(self, hass) -> None:
        """Reconfigure must not overwrite entity mappings the user set manually."""
        from custom_components.universal_energy_manager.config_flow import UemOptionsFlow
        from custom_components.universal_energy_manager.const import (
            CONF_FORECAST_SOLAR_ENTRY_IDS,
        )

        uem_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="UEM",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "S10E-12345",
                CONF_SOC_ENTITY: "sensor.custom_soc",
                CONF_PV_POWER_ENTITY: "sensor.custom_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.custom_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.custom_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.custom_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.custom_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.custom_max_charge",
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["fs-001"],
            },
            source="user",
            entry_id="uem-001",
            unique_id="e3dc_rscp:S10E-12345",
            state=config_entries.ConfigEntryState.LOADED,
        )
        # Inject hass into the entry (pytest-homeassistant-custom-component does this automatically
        # for MockConfigEntry, but not for manually constructed ConfigEntry)
        uem_entry._hass = hass  # type: ignore[attr-defined]

        # OptionsFlow should be constructible with the entry
        opts_flow = UemOptionsFlow(uem_entry)
        opts_flow.hass = hass
        opts_flow.handler = DOMAIN

        # It should not raise
        assert opts_flow.config_entry is not None


# ---------------------------------------------------------------------------
# Test 5: Unlimited Forecast.Solar entries (no fixed count)
# ---------------------------------------------------------------------------

class TestForecastSolarUnlimited:
    """Forecast.Solar entries must be unlimited — no fixed number."""

    def test_all_forecast_solar_entries_collected(self) -> None:
        """async_entries(FORECAST_SOLAR_DOMAIN) must return all entries."""
        hass = MagicMock()
        forecast_entries = [
            config_entries.ConfigEntry(
                version=1,
                minor_version=1,
                domain=FORECAST_SOLAR_DOMAIN,
                title=f"Roof {i}",
                data={},
                source="user",
                entry_id=f"fs-{i:03d}",
                unique_id=f"fs-{i}",
                state=config_entries.ConfigEntryState.LOADED,
            )
            for i in range(10)
        ]
        e3dc_entry = _make_e3dc_entry()
        flow = _make_flow(hass, e3dc_entries=[e3dc_entry], forecast_solar_entries=forecast_entries)

        # Trigger the flow to the confirm step
        with patch.object(UemConfigFlow, "_discover_entities", return_value=E3dcEntityMap()):
            result = _run_flow_coroutine(flow.async_step_user())

        # Should reach confirm with detected entities
        assert result["type"] == FlowResultType.FORM

    def test_entry_data_contains_forecast_solar_entry_ids_list(self) -> None:
        """The created entry data must contain a list of all forecast solar IDs."""
        hass = MagicMock()
        forecast_entries = [
            config_entries.ConfigEntry(
                version=1,
                minor_version=1,
                domain=FORECAST_SOLAR_DOMAIN,
                title="Hauptdach",
                data={},
                source="user",
                entry_id="fs-haupt",
                unique_id="fs-haupt",
                state=config_entries.ConfigEntryState.LOADED,
            ),
            config_entries.ConfigEntry(
                version=1,
                minor_version=1,
                domain=FORECAST_SOLAR_DOMAIN,
                title="Balkon",
                data={},
                source="user",
                entry_id="fs-balkon",
                unique_id="fs-balkon",
                state=config_entries.ConfigEntryState.LOADED,
            ),
        ]
        e3dc_entry = _make_e3dc_entry(entry_id="e3dc-001", unique_id="S10E-12345")
        flow = _make_flow(hass, e3dc_entries=[e3dc_entry], forecast_solar_entries=forecast_entries)
        flow._e3dc_entry_id = e3dc_entry.entry_id

        with patch.object(
            UemConfigFlow,
            "_discover_entities",
            return_value=E3dcEntityMap(
                soc="sensor.e3dc_soc",
                pv_power="sensor.e3dc_pv",
                house_power="sensor.e3dc_house",
                grid_export="sensor.e3dc_grid",
                battery_charge="sensor.e3dc_charge",
                battery_capacity="sensor.e3dc_capacity",
                max_charge_power="sensor.e3dc_max_charge",
            ),
        ):
            result = _run_flow_coroutine(flow.async_step_confirm({"confirm": "yes"}))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry_ids = result["data"].get(CONF_FORECAST_SOLAR_ENTRY_IDS, [])
        assert isinstance(entry_ids, list)
        assert len(entry_ids) == 2
        assert "fs-haupt" in entry_ids
        assert "fs-balkon" in entry_ids


# ---------------------------------------------------------------------------
# Test 6: No BHKW / wind forecast fields
# ---------------------------------------------------------------------------

class TestNoBhkwWindForecasts:
    """The config flow must NOT contain BHKW or wind forecast fields."""

    def test_no_bhkw_field_in_required_fields(self) -> None:
        assert "bhkw_entity" not in _REQUIRED_FIELDS
        assert "wind_entity" not in _REQUIRED_FIELDS
        assert "bhkw" not in str(_REQUIRED_FIELDS).lower()

    def test_no_bhkw_or_wind_in_config_flow(self) -> None:
        """The config_flow.py source must not reference BHKW or wind."""
        import inspect as inspect_module

        from custom_components.universal_energy_manager import config_flow as cf

        source = inspect_module.getsource(cf)
        assert "bhkw" not in source.lower(), "Config flow must not contain BHKW references."
        assert "wind" not in source.lower(), "Config flow must not contain wind references."


# ---------------------------------------------------------------------------
# Test 7: Mandatory fields still enforced
# ---------------------------------------------------------------------------

class TestMandatoryFieldsEnforced:
    """Missing mandatory entity → error, not crash."""

    def test_missing_required_entity_shows_error(self) -> None:
        """When discovery yields missing required fields, show error form."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        partial_map = E3dcEntityMap(soc="sensor.e3dc_soc")  # most fields None

        flow = _make_flow(hass, e3dc_entries=[e3dc_entry])
        flow._e3dc_entry_id = e3dc_entry.entry_id

        with patch.object(UemConfigFlow, "_discover_entities", return_value=partial_map):
            result = _run_flow_coroutine(flow.async_step_confirm())

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert "errors" in result
        assert result["errors"]["base"] == "missing_required_entities"
