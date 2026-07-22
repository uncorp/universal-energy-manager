"""Pytest conftest – provide thin mock Home Assistant helpers for unit tests.

Strategy: import the *real* Home Assistant installation (HA 2024.3.3 is
installed in the venv) so that classes like ``ConfigFlow``,
``SensorEntity`` and ``CoordinatorEntity`` work correctly.  The
``DataUpdateCoordinator`` is replaced by a lightweight stub so that
``_async_update_data`` (which would call ``build_live_state`` with
``MagicMock`` values) is never executed during collection.  The
``hass`` fixture provides a lightweight mock object.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_stub(name: str, **kwargs) -> ModuleType:
    """Create a thin mock module exposing given attributes."""
    mod = ModuleType(name)
    for k, v in kwargs.items():
        setattr(mod, k, v)
    return mod


# ---------------------------------------------------------------------------
# 1. Import real HA modules so their classes are available.
# ---------------------------------------------------------------------------
_real_ha_ok = False
try:
    import homeassistant  # noqa: F401
    from homeassistant import (
        config_entries,  # noqa: F401
        const,  # noqa: F401
        core,  # noqa: F401
    )
    from homeassistant.components import sensor as _sensor_mod  # noqa: F401
    from homeassistant.components.sensor import SensorEntity  # noqa: F401
    from homeassistant.config_entries import ConfigFlow  # noqa: F401
    from homeassistant.helpers import entity as _ent_mod  # noqa: F401
    from homeassistant.helpers import entity_platform as _ep_mod  # noqa: F401
    from homeassistant.helpers import entity_registry as _er_mod  # noqa: F401
    from homeassistant.helpers.entity_platform import AddEntitiesCallback  # noqa: F401
    from homeassistant.helpers.update_coordinator import (
        CoordinatorEntity as _RealCE,  # noqa: F401
    )
    from homeassistant.helpers.update_coordinator import (
        DataUpdateCoordinator as _RealDUC,  # noqa: F401
    )
    from homeassistant.util import dt as _dt_mod  # noqa: F401
    _real_ha_ok = True
except Exception:
    pass

# ---------------------------------------------------------------------------
# 2. Lightweight DataUpdateCoordinator stub – no _async_update_data
# ---------------------------------------------------------------------------

class _DataUpdateCoordinator:
    """Minimal DUC stub. Calls _async_update_data if defined by subclass."""

    def __init__(self, hass=None, *args, **kwargs):
        self.hass = hass
        self.data = None
        self.last_update = None
        self.pending_refresh = False
        self._listeners: list = []
        self._on_unload_callbacks: list = []
        self.name = "universal_energy_manager"

    async def async_refresh(self):
        if hasattr(self, '_async_update_data'):
            self.data = await self._async_update_data()
        return self.data

    async def async_config_entry_first_refresh(self):
        return await self.async_refresh()

    async def async_add_listener(self, callback=None, update_option=None):
        if callback is not None:
            self._listeners.append(callback)
        return MagicMock()

    def async_shutdown(self):
        for cb in self._on_unload_callbacks:
            if callable(cb):
                try:
                    cb()
                except Exception:
                    pass
        self._on_unload_callbacks.clear()

    def async_on_unload(self, fn):
        self._on_unload_callbacks.append(fn)

    @classmethod
    def __class_getitem__(cls, item):
        return cls


class _CoordinatorEntity:
    """Minimal CoordinatorEntity stub supporting generic subscript."""

    def __init__(self, coordinator=None, *args, **kwargs):
        self.coordinator = coordinator
        self._attr_has_entity_name = True
        self.name = None
        self._attr_name = None

    @classmethod
    def __class_getitem__(cls, item):
        return cls


# Install the stub in sys.modules so any import of the real module
# (which was imported above) gets replaced by the stub.
if _real_ha_ok:
    sys.modules["homeassistant.helpers.update_coordinator"] = _make_stub(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=_DataUpdateCoordinator,
        CoordinatorEntity=_CoordinatorEntity,
    )


# ---------------------------------------------------------------------------
# 3. pytest-homeassistant-custom_component stub
# ---------------------------------------------------------------------------
_phacc = _make_stub("pytest_homeassistant_custom_component")
_phacc_common = _make_stub("pytest_homeassistant_custom_component.common")
_phacc_common.MockConfigEntry = MagicMock
_phacc_common.mock_entity_picture = MagicMock
sys.modules["pytest_homeassistant_custom_component"] = _phacc
sys.modules["pytest_homeassistant_custom_component.common"] = _phacc_common

# Transitive deps
for _mod_name, _mod_kwargs in [
    ("async_interrupt", {"interrupt": MagicMock}),
    ("awesomeversion", {"AwesomeVersion": MagicMock}),
    ("pytz", {"utc": MagicMock()}),
    ("slugify", {"slugify": MagicMock()}),
    ("voluptuous", {"Schema": type("Schema", (), {})}),
    ("voluptuous.humanize", {}),
    ("aiohttp", {}),
    ("propcache", {}),
    ("propcache.api", {}),
    ("orjson", {"dumps": MagicMock(), "loads": MagicMock()}),
    ("httpx", {}),
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_stub(_mod_name, **_mod_kwargs)


# ---------------------------------------------------------------------------
# Minimal hass fixture
# ---------------------------------------------------------------------------


class _MockStates:
    """Minimal mock for hass.states that returns usable State-like objects."""
    def __init__(self):
        self._states: dict[str, MagicMock] = {}

    def async_set(self, entity_id: str, state: str, attributes: dict | None = None) -> None:
        attrs = attributes or {}
        uom = attrs.get("unit_of_measurement", None)
        self._states[entity_id] = MagicMock(
            entity_id=entity_id,
            state=str(state),
            attributes=attrs,
            last_changed=datetime.now(UTC),
            last_updated=datetime.now(UTC),
            _uom=uom,
        )
        # Make state convertible to float for numeric sensors
        try:
            float(state)
        except (ValueError, TypeError):
            pass

    def get(self, entity_id: str) -> MagicMock | None:
        return self._states.get(entity_id)

    def async_all(self) -> list[MagicMock]:
        return list(self._states.values())

    def __getitem__(self, key):
        return self._states[key]


class _MockConfig:
    """Minimal mock for hass.config."""
    time_zone = MagicMock()
    location_name = "Test Home"
    country = "DE"
    latitude = 0.0
    longitude = 0.0
    elevation = 0


class _MockConfigEntries:
    """Minimal mock for hass.config_entries."""
    def __init__(self):
        self._entries: list[MagicMock] = []
        self.flow = AsyncMock()

    def async_entries(self, domain=None):
        if domain is None:
            return self._entries
        return [e for e in self._entries if e.domain == domain]

    def add(self, entry):
        self._entries.append(entry)

    async def async_unload_platforms(self, entry):
        return True

    async def async_forward_entry_setups(self, entry, platforms):
        return True


class _MockServices:
    """Minimal mock for hass.services."""
    def async_call(self, *args, **kwargs):
        pass

    def call(self, *args, **kwargs):
        pass

    def fire(self, *args, **kwargs):
        pass


class MockHass:
    """Minimal HomeAssistant fixture replacement."""
    def __init__(self):
        self.states = _MockStates()
        self.config = _MockConfig()
        self.config_entries = _MockConfigEntries()
        self.services = _MockServices()
        self.data = {}


@pytest.fixture()
def hass():
    """Provide a minimal hass fixture without full HA installation."""
    h = MockHass()
    return h


@pytest.fixture()
def enable_custom_integrations(hass):
    """Enable custom integrations for config_flow tests."""
    return None
