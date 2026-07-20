"""Constants for UEM."""

DOMAIN = "universal_energy_manager"
E3DC_RSCP_DOMAIN = "e3dc_rscp"

CONF_E3DC_CONFIG_ENTRY_ID = "e3dc_config_entry_id"
CONF_E3DC_SOURCE_UNIQUE_ID = "e3dc_source_unique_id"
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_POWER_ENTITY = "pv_power_entity"
CONF_HOUSE_POWER_ENTITY = "house_power_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"
CONF_BATTERY_CHARGE_ENTITY = "battery_charge_entity"
CONF_BATTERY_CAPACITY_ENTITY = "battery_capacity_entity"
CONF_MAX_CHARGE_POWER_ENTITY = "max_charge_power_entity"
CONF_FORECAST_ENTITY = "forecast_entity"
CONF_FORECAST_SOLAR_ENTRY_IDS = "forecast_solar_entry_ids"
CONF_STRATEGY = "strategy"
FORECAST_SOLAR_DOMAIN = "forecast_solar"

CONF_TARGET_SOC_PCT = "target_soc_pct"
CONF_CHARGE_END = "charge_end"

STRATEGY_PV_FIRST = "pv_first"
STRATEGY_BATTERY_FIRST = "battery_first"
STRATEGY_BALANCED = "balanced"

DEFAULT_TARGET_SOC_PCT = 95.0
DEFAULT_CHARGE_END_HOURS = 6
DEFAULT_STRATEGY = STRATEGY_PV_FIRST

STRATEGY_OPTIONS = [STRATEGY_PV_FIRST, STRATEGY_BATTERY_FIRST, STRATEGY_BALANCED]
