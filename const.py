"""Constants for the Solar Savings integration."""

DOMAIN = "solar_savings"

# Config entry keys
CONF_SOLAR_POWER_SENSOR = "solar_power_sensor"
CONF_SOLAR_ENERGY_TODAY = "solar_energy_today"
CONF_SOLAR_ENERGY_MONTH = "solar_energy_month"
CONF_ELECTRICITY_RATE = "electricity_rate"
CONF_CURRENCY_SYMBOL = "currency_symbol"
CONF_SETUP_COST = "setup_cost"

# Defaults
DEFAULT_ELECTRICITY_RATE = 0.33
DEFAULT_CURRENCY_SYMBOL = "£"
DEFAULT_SETUP_COST = 5000.0

# Sensor unique ID suffixes
SENSOR_SAVINGS_RATE = "savings_rate"
SENSOR_SAVINGS_TODAY = "savings_today"
SENSOR_SAVINGS_MONTH = "savings_month"
SENSOR_SAVINGS_LIFETIME = "savings_lifetime"
SENSOR_PAYBACK_REMAINING = "payback_remaining"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"
