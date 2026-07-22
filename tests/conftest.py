"""Pytest conftest – provide thin mock Home Assistant helpers for unit tests.

Strategy: inject a complete homeassistant stub into sys.modules *before* any
test module (or custom_components code) tries to import real HA.  This
conftest runs at the very start of pytest collection, so all submodules are
available before custom_components/universal_energy_manager/__init__.py is
imported.
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


# ===========================================================================
# 0. Stub modules — these MUST be injected before any HA import
# ===========================================================================

# --- homeassistant.const ---
class _Platform:
    SENSOR = "sensor"
Platform = _Platform

ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

class _UnitOfPower:
    WATT = "W"
UnitOfPower = _UnitOfPower

# --- homeassistant.core ---
HomeAssistant = MagicMock

class _State:
    """Minimal State stub that stores entity_id, state, attributes."""
    def __init__(self, entity_id, state, attributes=None,
                 last_changed=None, last_updated=None,
                 context=None, time_created=None, updated=None):
        self.entity_id = entity_id
        self.state = str(state)
        self.attributes = attributes or {}
        self.last_changed = last_changed or datetime.now(UTC)
        self.last_updated = last_updated or datetime.now(UTC)
        self.context = context
        self.time_created = time_created
        self.updated = updated

State = _State

def callback(f):
    """HA callback decorator – just return the function."""
    return f

# --- homeassistant.config_entries ---
class ConfigEntry:
    """Minimal ConfigEntry that accepts keyword args like the real one."""
    def __init__(self, *, version, minor_version, domain, title, data,
                 source, entry_id, unique_id=None, options=None,
                 pref_disable_new_entities=None, pref_disable_polling=None,
                 options_version=None, released=False,
                 **kwargs):
        self.version = version
        self.minor_version = minor_version
        self.domain = domain
        self.title = title
        self.data = data
        self.source = source
        self.entry_id = entry_id
        self.unique_id = unique_id
        self.options = options or {}
        self.pref_disable_new_entities = pref_disable_new_entities
        self.pref_disable_polling = pref_disable_polling
        self.options_version = options_version
        self._on_unload = []

    def async_on_unload(self, fn):
        self._on_unload.append(fn)

    def async_will_remove_from_hass(self):
        for fn in self._on_unload:
            try:
                fn()
            except Exception:
                pass

class ConfigFlow:
    """Stub that accepts domain= keyword in __init_subclass__ and provides flow methods."""
    domain = None
    handler = None
    context = {}
    step_id = "user"
    _flow_result = None
    _async_current_entries_data = []

    def __init_subclass__(cls, domain=None, **kwargs):
        cls.domain = domain

    def _async_current_entries(self):
        return self._async_current_entries_data

    async def async_step_user(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_init(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_reconfigure(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_confirm(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_no_e3dc_choice(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_manual_mapping(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_step_source(self, user_input=None):
        return self._flow_result or MagicMock()

    async def async_get_progress(self):
        return []

    async def async_show_form(
        self, *, step_id, errors=None, description_placeholders=None, last_step=None
    ):
        return MagicMock(
            type=FlowResultType.FORM,
            step_id=step_id,
            errors=errors or {},
            description_placeholders=description_placeholders or {},
        )

    async def async_create_entry(self, title=None, data=None):
        return MagicMock(
            type=FlowResultType.CREATE,
            title=title or "",
            data=data or {},
        )

    async def async_abort(self, *, reason):
        return MagicMock(
            type=FlowResultType.ABORT,
            reason=reason,
        )

    async def async_forward_entry_setup(self, hass, entry):
        return True

class ConfigEntryState:
    LOADED = "loaded"
    SETUP_ERROR = "setup_error"
    MIGRATION_FLOW = "migration_flow"
    SETUP_RETRY = "setup_retry"
    READY = "ready"

# --- homeassistant.data_entry_flow ---
class FlowResultType:
    CREATE = "create"
    FORM = "form"
    COMPLETE = "complete"
    ABORT = "abort"

class FlowResult:
    pass

# util
class _DtMod:
    utc = MagicMock()
    def now(self):
        return datetime.now(UTC)
    def utcnow(self):
        return datetime.now(UTC)
    async def async_get_time_zone(self, tz):
        import pytz
        return pytz.timezone(tz) if tz else UTC
    def parse_datetime(self, s):
        return None
_dt_mod_local = _DtMod()

dt_util = _DtMod()

# --- homeassistant.helpers ---
class SensorEntity:
    """Minimal SensorEntity that maps _attr_native_* to public properties."""
    _attr_native_unit_of_measurement = None
    _attr_native_value = None
    _attr_has_entity_name = True

    @property
    def unit_of_measurement(self):
        if self._attr_native_unit_of_measurement is not None:
            return self._attr_native_unit_of_measurement
        return getattr(self, '_attr_unit_of_measurement', None)

    @property
    def native_value(self):
        if self._attr_native_value is not None:
            return self._attr_native_value
        return getattr(self, '_attr_value', None)


class CoordinatorEntity:
    _attr_has_entity_name = True
    def __init__(self, coordinator=None, *args, **kwargs):
        self.coordinator = coordinator
        self.name = None
        self._attr_name = None

    @classmethod
    def __class_getitem__(cls, item):
        return cls

class DataUpdateCoordinator:
    """Stub DUC supporting __class_getitem__ for type hints."""
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

AddEntitiesCallback = MagicMock

# --- homeassistant.helpers.entity_registry ---
class Registry:
    pass


# ===========================================================================
# 1. Inject stubs into sys.modules
# ===========================================================================

_ha_root = _make_stub("homeassistant")

_ha_const = _make_stub("homeassistant.const",
    Platform=Platform,
    ATTR_UNIT_OF_MEASUREMENT=ATTR_UNIT_OF_MEASUREMENT,
    UnitOfPower=UnitOfPower,
)
_ha_root.const = _ha_const

_ha_core = _make_stub("homeassistant.core",
    HomeAssistant=HomeAssistant,
    State=State,
    callback=callback,
)
_ha_root.core = _ha_core

_ha_config_entries = _make_stub("homeassistant.config_entries",
    ConfigEntry=ConfigEntry,
    ConfigFlow=ConfigFlow,
    ConfigEntryState=ConfigEntryState,
)
_ha_root.config_entries = _ha_config_entries

_ha_data_entry_flow = _make_stub("homeassistant.data_entry_flow",
    FlowResultType=FlowResultType,
    FlowResult=FlowResult,
    AbortFlow=Exception,
)
_ha_root.data_entry_flow = _ha_data_entry_flow

_ha_util = _make_stub("homeassistant.util")
_ha_util_dt = _make_stub("homeassistant.util.dt",
    dt=_DtMod(),
    utc=_DtMod().utc,
)
_ha_util.dt = _DtMod()
_ha_root.util = _ha_util

_ha_components = _make_stub("homeassistant.components")
_ha_components_sensor = _make_stub("homeassistant.components.sensor",
    SensorEntity=SensorEntity,
)
_ha_components.sensor = _ha_components_sensor
_ha_root.components = _ha_components

_ha_helpers = _make_stub("homeassistant.helpers")
_ha_helpers_entity = _make_stub("homeassistant.helpers.entity",
    Entity=MagicMock,
)
_ha_helpers.entity = _ha_helpers_entity

_ha_helpers_entity_platform = _make_stub(
    "homeassistant.helpers.entity_platform",
    AddEntitiesCallback=AddEntitiesCallback,
)
_ha_helpers.entity_platform = _ha_helpers_entity_platform

_ha_helpers_entity_registry = _make_stub(
    "homeassistant.helpers.entity_registry",
    Registry=Registry,
)
_ha_helpers.entity_registry = _ha_helpers_entity_registry

_ha_helpers_uc = _make_stub("homeassistant.helpers.update_coordinator",
    DataUpdateCoordinator=DataUpdateCoordinator,
    CoordinatorEntity=CoordinatorEntity,
)
_ha_helpers.update_coordinator = _ha_helpers_uc

# Register all
for _mod in [_ha_root, _ha_const, _ha_core, _ha_config_entries,
             _ha_data_entry_flow, _ha_util, _ha_util_dt, _ha_components,
             _ha_components_sensor, _ha_helpers, _ha_helpers_entity,
             _ha_helpers_entity_platform, _ha_helpers_entity_registry,
             _ha_helpers_uc]:
    sys.modules[_mod.__name__] = _mod


# ===========================================================================
# 2. pytest-homeassistant-custom_component stub
# ===========================================================================
_phacc = _make_stub("pytest_homeassistant_custom_component")
_phacc_common = _make_stub("pytest_homeassistant_custom_component.common")


class _MockConfigEntry(ConfigEntry):
    """ConfigEntry that acts as a mock but uses the real constructor."""
    def __init__(self, *, domain, data=None, title="", entry_id=None,
                 source="user", unique_id=None, options=None,
                 version=1, minor_version=1, **kwargs):
        super().__init__(
            version=version,
            minor_version=minor_version,
            domain=domain,
            title=title,
            data=data or {},
            source=source,
            entry_id=entry_id or f"mock-{domain}",
            unique_id=unique_id,
            options=options or {},
            **kwargs,
        )


_phacc_common.MockConfigEntry = _MockConfigEntry
_phacc_common.mock_entity_picture = MagicMock
sys.modules["pytest_homeassistant_custom_component"] = _phacc
sys.modules["pytest_homeassistant_custom_component.common"] = _phacc_common

for _mod_name, _mod_kwargs in [
    ("async_interrupt", {"interrupt": MagicMock}),
    ("awesomeversion", {"AwesomeVersion": MagicMock}),
    ("pytz", {"utc": MagicMock()}),
    ("slugify", {"slugify": MagicMock()}),
    ("voluptuous", {
        "Schema": type("Schema", (), {}),
        "Optional": lambda k, **kw: k,
        "Required": lambda k, **kw: k,
    }),
    ("voluptuous.humanize", {}),
    ("aiohttp", {}),
    ("propcache", {}),
    ("propcache.api", {}),
    ("orjson", {"dumps": MagicMock(), "loads": MagicMock()}),
    ("httpx", {}),
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_stub(_mod_name, **_mod_kwargs)


# ===========================================================================
# 3. hass fixture
# ===========================================================================

class _MockStates:
    def __init__(self):
        self._states: dict[str, MagicMock] = {}

    def async_set(self, entity_id: str, state: str, attributes: dict | None = None) -> None:
        self._states[entity_id] = MagicMock(
            entity_id=entity_id,
            state=str(state),
            attributes=attributes or {},
            last_changed=datetime.now(UTC),
            last_updated=datetime.now(UTC),
        )

    def get(self, entity_id: str) -> MagicMock | None:
        return self._states.get(entity_id)

    def async_all(self) -> list[MagicMock]:
        return list(self._states.values())

    def __getitem__(self, key):
        return self._states[key]


class _MockConfig:
    time_zone = MagicMock()
    location_name = "Test Home"
    country = "DE"
    latitude = 0.0
    longitude = 0.0
    elevation = 0


class _MockConfigEntries:
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
    def async_call(self, *args, **kwargs):
        pass
    def call(self, *args, **kwargs):
        pass
    def fire(self, *args, **kwargs):
        pass


class MockHass:
    def __init__(self):
        self.states = _MockStates()
        self.config = _MockConfig()
        self.config_entries = _MockConfigEntries()
        self.services = _MockServices()
        self.data = {}


@pytest.fixture()
def hass():
    return MockHass()


@pytest.fixture()
def enable_custom_integrations(hass):
    return None
