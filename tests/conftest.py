"""Pytest conftest – provide thin mock Home Assistant helpers for unit tests.

Strategy: Real HA is installed in the venv. Only inject stubs for modules
that do NOT exist in the real HA install. Real HA modules are left untouched
so the pytest-homeassistant-custom-component plugin can traverse the
homeassistant.helpers hierarchy without hitting a stub ModuleType.
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
# 0. Stub classes / functions (no injection yet)
# ===========================================================================

class _Platform:
    SENSOR = "sensor"
Platform = _Platform

ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

class _UnitOfPower:
    WATT = "W"
UnitOfPower = _UnitOfPower

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

class _FlowResult(dict):
    """A dict subclass with a .type attribute for FlowResult compatibility."""
    def __init__(self, type_, **kwargs):
        super().__init__(**kwargs)
        self["type"] = type_
        self.type = type_

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
        if hasattr(self, 'domain') and self.domain and hasattr(self, 'hass'):
            return self.hass.config_entries.async_entries(self.domain)
        return self._async_current_entries_data

    def async_step_user(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_init(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_reconfigure(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_confirm(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_no_e3dc_choice(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_manual_mapping(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_step_source(self, user_input=None):
        return self._flow_result or _FlowResult("form")

    def async_get_progress(self):
        return []

    def async_show_form(
        self, *, step_id, errors=None, description_placeholders=None,
        last_step=None, data_schema=None
    ):
        return _FlowResult(
            FlowResultType.FORM,
            step_id=step_id,
            errors=errors or {},
            description_placeholders=description_placeholders or {},
            data_schema=data_schema,
        )

    def async_create_entry(self, title=None, data=None):
        return _FlowResult(
            FlowResultType.CREATE_ENTRY,
            title=title or "",
            data=data or {},
        )

    def async_abort(self, *, reason, description_placeholders=None):
        return _FlowResult(
            FlowResultType.ABORT,
            reason=reason,
            description_placeholders=description_placeholders or {},
        )

    def async_forward_entry_setup(self, hass, entry):
        return True

    async def async_set_unique_id(self, unique_id=None):
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self, *, upload_content=None):
        if hasattr(self, 'hass') and hasattr(self, '_unique_id') and self._unique_id:
            from custom_components.universal_energy_manager.const import DOMAIN
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, self._unique_id
            ) if hasattr(self.hass.config_entries, 'async_entry_for_domain_unique_id') else None
            if existing is not None:
                from homeassistant.data_entry_flow import AbortFlow
                raise AbortFlow("already_configured")

class ConfigEntryState:
    LOADED = "loaded"
    SETUP_ERROR = "setup_error"
    MIGRATION_FLOW = "migration_flow"
    SETUP_RETRY = "setup_retry"
    READY = "ready"
    NOT_LOADED = "not_loaded"

class FlowResultType:
    CREATE = "create"
    CREATE_ENTRY = "create_entry"
    FORM = "form"
    COMPLETE = "complete"
    ABORT = "abort"

class FlowResult:
    pass

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

dt_util = _DtMod()

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

class _MockRegistry:
    async def async_get(self, hass):
        return self
    entities = {}

class Registry:
    pass

_er_mock = _MockRegistry()
def er_async_get(hass):
    return _er_mock


# ===========================================================================
# 1. Inject HA stubs ONLY when real HA is NOT installed
# ===========================================================================

# List of real HA submodules that already exist in sys.modules.
# When real HA is installed, these are real modules and must NOT be replaced.
_REAL_HA_MODULES = {
    "homeassistant",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
    "homeassistant.util",
    "homeassistant.util.dt",
    "homeassistant.util.logging",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.helpers",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.entity_registry",
    "homeassistant.helpers.update_coordinator",
}

# Check if real HA is available
_HA_AVAILABLE = "homeassistant" in sys.modules

# --- Inject HA stubs when real HA is NOT installed ---
if not _HA_AVAILABLE:
    _ha_root = _make_stub("homeassistant")
    sys.modules["homeassistant"] = _ha_root

    # Build parent chain: homeassistant.config_entries etc.
    for _sub in [
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.config_entries",
        "homeassistant.data_entry_flow",
        "homeassistant.util",
        "homeassistant.util.dt",
        "homeassistant.util.logging",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.helpers",
        "homeassistant.helpers.entity",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.entity_registry",
        "homeassistant.helpers.update_coordinator",
        "homeassistant.helpers.script",
    ]:
        if _sub not in sys.modules:
            sys.modules[_sub] = _make_stub(_sub)

    # Populate namespace packages
    _ha_const = sys.modules.get("homeassistant.const")
    if _ha_const:
        _ha_const.Platform = Platform
        _ha_const.ATTR_UNIT_OF_MEASUREMENT = ATTR_UNIT_OF_MEASUREMENT
        _ha_const.UnitOfPower = UnitOfPower

    _ha_core = sys.modules.get("homeassistant.core")
    if _ha_core:
        _ha_core.HomeAssistant = HomeAssistant
        _ha_core.callback = callback
        _ha_core.State = State

    _ha_config_entries = sys.modules.get("homeassistant.config_entries")
    if _ha_config_entries:
        _ha_config_entries.ConfigEntry = ConfigEntry
        _ha_config_entries.ConfigEntryState = ConfigEntryState
        _ha_config_entries.ConfigFlow = ConfigFlow

    _ha_data_entry_flow = sys.modules.get("homeassistant.data_entry_flow")
    if _ha_data_entry_flow:
        _ha_data_entry_flow.FlowResult = FlowResult
        _ha_data_entry_flow.FlowResultType = FlowResultType
        _ha_data_entry_flow.AbortFlow = Exception

    _ha_helpers = sys.modules.get("homeassistant.helpers")
    if _ha_helpers:
        pass

    _ha_helpers_entity = sys.modules.get("homeassistant.helpers.entity")
    if _ha_helpers_entity:
        _ha_helpers_entity.SensorEntity = SensorEntity
        _ha_helpers_entity.CoordinatorEntity = CoordinatorEntity

    _ha_helpers_upd = sys.modules.get("homeassistant.helpers.update_coordinator")
    if _ha_helpers_upd:
        _ha_helpers_upd.DataUpdateCoordinator = DataUpdateCoordinator
        _ha_helpers_upd.CoordinatorEntity = CoordinatorEntity

    _ha_helpers_er = sys.modules.get("homeassistant.helpers.entity_registry")
    if _ha_helpers_er:
        _ha_helpers_er.Registry = Registry
        _ha_helpers_er.async_get = er_async_get
        _ha_helpers_er.async_entries_for_config_entry = MagicMock(return_value=[])

    _ha_helpers_ep = sys.modules.get("homeassistant.helpers.entity_platform")
    if _ha_helpers_ep:
        _ha_helpers_ep.AddEntitiesCallback = AddEntitiesCallback

    _ha_components_sensor = sys.modules.get("homeassistant.components.sensor")
    if _ha_components_sensor:
        _ha_components_sensor.SensorEntity = SensorEntity

    _ha_util = sys.modules.get("homeassistant.util")
    if _ha_util:
        pass
    _ha_util_dt = sys.modules.get("homeassistant.util.dt")
    if _ha_util_dt:
        _ha_util_dt.utc = dt_util.utc
        _ha_util_dt.now = dt_util.now
        _ha_util_dt.utcnow = dt_util.utcnow
        _ha_util_dt.async_get_time_zone = dt_util.async_get_time_zone
        _ha_util_dt.parse_datetime = dt_util.parse_datetime

    _ha_util_logging = sys.modules.get("homeassistant.util.logging")
    if _ha_util_logging:
        _ha_util_logging.log_exception = lambda *a, **k: None
        _ha_util_logging.catch_log_exception = lambda *a, **k: None
        _ha_util_logging.catch_log_coro_exception = lambda *a, **k: None
        _ha_util_logging.async_create_catching_coro = lambda *a, **k: None
        _ha_util_logging.async_activate_log_queue_handler = lambda *a, **k: None


# --- pytest-homeassistant-custom_component stub ---
# This module does NOT exist in real HA — we must provide it.
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

# --- Other non-HA third-party stubs (only if not already present) ---
for _mod_name, _mod_kwargs in [
    ("async_interrupt", {"interrupt": MagicMock}),
    ("awesomeversion", {"AwesomeVersion": MagicMock}),
    ("pytz", {"utc": MagicMock()}),
    ("slugify", {"slugify": MagicMock()}),
    ("voluptuous", {
        "Schema": lambda schema, **kw: type("Schema", (), {
            "schema": schema if isinstance(schema, dict) else {},
            "_compiled": None,
            "extra": kw.get("extra", None),
        })(),
        "Optional": lambda k, **kw: k,
        "Required": lambda k, **kw: k,
        "In": lambda container: type("In", (), {"container": container})(),
        "All": lambda *args: args[0] if args else None,
        "Length": lambda minimum, maximum=None, **kw: None,
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
# 2. hass fixture
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
