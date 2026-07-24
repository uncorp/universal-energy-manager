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
CONF_MANUAL_ENTITIES = "manual_entities"
CONF_STRATEGY = "strategy"
FORECAST_SOLAR_DOMAIN = "forecast_solar"

# --- Power mode semantics (signed vs. separate) ---
CONF_BATTERY_POWER_MODE = "battery_power_mode"
CONF_BATTERY_POWER_SIGN_CONVENTION = "battery_power_sign_convention"
CONF_BATTERY_DISCHARGE_ENTITY = "battery_discharge_entity"
CONF_BATTERY_MANUAL_CAPACITY_KWH = "battery_manual_capacity_kwh"
CONF_MAX_CHARGE_MANUAL_POWER_W = "max_charge_manual_power_w"

CONF_GRID_POWER_MODE = "grid_power_mode"
CONF_GRID_POWER_SIGN_CONVENTION = "grid_power_sign_convention"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"

BATTERY_POWER_MODE_SIGNED = "signed"
BATTERY_POWER_MODE_SEPARATE = "separate"
BATTERY_POWER_MODES = [BATTERY_POWER_MODE_SIGNED, BATTERY_POWER_MODE_SEPARATE]

GRID_POWER_MODE_SIGNED = "signed"
GRID_POWER_MODE_SEPARATE = "separate"
GRID_POWER_MODES = [GRID_POWER_MODE_SIGNED, GRID_POWER_MODE_SEPARATE]

SIGNED_CONVENTION_POS_CHARGE_EXPORT = "positive_is_charging_export"
SIGNED_CONVENTION_NEG_CHARGE_EXPORT = "negative_is_charging_export"
SIGNED_CONVENTION_POS_DISCHARGE_IMPORT = "positive_is_discharging_import"
SIGNED_CONVENTION_NEG_DISCHARGE_IMPORT = "negative_is_discharging_import"

CONF_TARGET_SOC_PCT = "target_soc_pct"
CONF_CHARGE_END = "charge_end"

STRATEGY_PV_FIRST = "pv_first"
STRATEGY_BATTERY_FIRST = "battery_first"
STRATEGY_BALANCED = "balanced"

DEFAULT_TARGET_SOC_PCT = 95.0
DEFAULT_CHARGE_END_HOURS = 6
DEFAULT_STRATEGY = STRATEGY_PV_FIRST

STRATEGY_OPTIONS = [STRATEGY_PV_FIRST, STRATEGY_BATTERY_FIRST, STRATEGY_BALANCED]

# --- Shadow status ---
SHADOW_STATUS = "Shadow – keine aktive Steuerung"
SHADOW_STATUS_UNVOLLSTANDIG = "Shadow – Einrichtung unvollständig"

# --- Mapping: config key -> E3dcEntityMap attribute name ---
_ENT_MAP_LOOKUP: dict[str, str] = {
    CONF_SOC_ENTITY: "soc",
    CONF_PV_POWER_ENTITY: "pv_power",
    CONF_HOUSE_POWER_ENTITY: "house_power",
    CONF_GRID_EXPORT_ENTITY: "grid_export",
    CONF_BATTERY_CHARGE_ENTITY: "battery_charge",
    CONF_BATTERY_DISCHARGE_ENTITY: "battery_discharge",
    CONF_BATTERY_CAPACITY_ENTITY: "battery_capacity",
    CONF_MAX_CHARGE_POWER_ENTITY: "max_charge_power",
}
