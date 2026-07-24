"""Regression tests for UEM __init__.py async_setup_entry lifecycle.

Covers:
- async_setup_entry creates the coordinator, performs first refresh,
  stores it in hass.data, and forwards platform setup.
- Shadow-only: no service calls, no active control, no credentials written.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager import (
    DOMAIN,
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.universal_energy_manager.coordinator import (
    ShadowData,
    UemShadowCoordinator,
)


@pytest.mark.asyncio
async def test_setup_entry_creates_coordinator_and_stores_in_hass_data() -> None:
    """async_setup_entry must instantiate the coordinator and persist it in hass.data."""
    hass = MagicMock()
    hass.data = {}
    entry = MockConfigEntry(domain=DOMAIN)

    mock_coordinator = MagicMock(spec=UemShadowCoordinator)
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with patch(
        "custom_components.universal_energy_manager.UemShadowCoordinator",
        return_value=mock_coordinator,
    ), patch.object(
        hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN][entry.entry_id] is mock_coordinator
    mock_coordinator.async_config_entry_first_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_setup_entry_forwards_sensor_platform_only() -> None:
    """async_setup_entry must forward platform setup for sensors only."""
    hass = MagicMock()
    hass.data = {}
    entry = MockConfigEntry(domain=DOMAIN)

    mock_coordinator = MagicMock(spec=UemShadowCoordinator)
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with patch(
        "custom_components.universal_energy_manager.UemShadowCoordinator",
        return_value=mock_coordinator,
    ), patch.object(
        hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
    ) as forward_mock:
        await async_setup_entry(hass, entry)

    forward_mock.assert_called_once_with(entry, PLATFORMS)
    assert PLATFORMS == ["sensor"]


@pytest.mark.asyncio
async def test_setup_entry_with_shadow_data_produces_valid_state() -> None:
    """When the coordinator refreshes successfully, hass.data holds ShadowData."""
    hass = MagicMock()
    hass.data = {}
    entry = MockConfigEntry(domain=DOMAIN)

    coordinator = UemShadowCoordinator(hass, entry)
    coordinator.data = ShadowData(
        status="Shadow – keine aktive Steuerung",
        decision="Livewerte gueltig.",
        planned_charge_limit_w=5000.0,
        error=None,
        forecast_connected=True,
        pv_power_w=3200.0,
        house_power_w=800.0,
        strategy="pv_first",
    )
    coordinator.async_config_entry_first_refresh = AsyncMock(return_value=None)

    with patch(
        "custom_components.universal_energy_manager.UemShadowCoordinator",
        return_value=coordinator,
    ), patch.object(
        hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert coordinator.data is not None
    assert coordinator.data.status == "Shadow – keine aktive Steuerung"
    assert coordinator.data.commands_sent is False


@pytest.mark.asyncio
async def test_platforms_is_sensor_only() -> None:
    """PLATFORMS must contain only the sensor platform — no switch/select."""
    assert PLATFORMS == ["sensor"]
    for plat in PLATFORMS:
        assert plat not in ("switch", "select", "number", "button")


@pytest.mark.asyncio
async def test_async_setup_entry_imports_no_service_modules() -> None:
    """Shadow safety: __init__.py must never import homeassistant.services."""
    import ast

    with open(
        "custom_components/universal_energy_manager/__init__.py"
    ) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "services" not in alias.name, (
                        f"Shadow violation: __init__.py imports {alias.name}"
                    )
            else:
                assert "services" not in (module or ""), (
                    f"Shadow violation: __init__.py imports {module}"
                )


@pytest.mark.asyncio
async def test_async_unload_entry_cleans_data_on_success() -> None:
    """When unload succeeds, hass.data[DOMAIN][entry_id] must be removed."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data[DOMAIN][entry.entry_id] = MagicMock()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_unload_entry_keeps_data_on_failure() -> None:
    """If unload fails, entry data must NOT be removed."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data[DOMAIN][entry.entry_id] = MagicMock()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await async_unload_entry(hass, entry)

    assert result is False
    assert entry.entry_id in hass.data[DOMAIN]
