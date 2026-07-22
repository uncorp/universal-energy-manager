"""Regression tests for UEM __init__.py lifecycle (Shadow-only).

Covers:
- async_unload_entry cleans up hass.data and returns True on success.
- async_unload_entry returns False when the sensor platform cannot unload.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager import DOMAIN


# ---------------------------------------------------------------------------
# async_unload_entry: successful cleanup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unload_entry_clears_hass_data(hass: HomeAssistant) -> None:
    """When unload succeeds, hass.data[DOMAIN][entry_id] must be removed."""
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = MagicMock()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ):
        from custom_components.universal_energy_manager import async_unload_entry

        result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]


# ---------------------------------------------------------------------------
# async_unload_entry: platform unload fails
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unload_entry_platform_failure_returns_false(hass: HomeAssistant) -> None:
    """If the sensor platform cannot unload, the entry data must be kept."""
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = MagicMock()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        from custom_components.universal_energy_manager import async_unload_entry

        result = await async_unload_entry(hass, entry)

    assert result is False
    # Data must NOT be removed when unload failed
    assert entry.entry_id in hass.data[DOMAIN]
