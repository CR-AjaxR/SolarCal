"""Sensor platform for Solar Savings."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CURRENCY_SYMBOL,
    CONF_ELECTRICITY_RATE,
    CONF_SETUP_COST,
    CONF_SOLAR_ENERGY_MONTH,
    CONF_SOLAR_ENERGY_TODAY,
    CONF_SOLAR_POWER_SENSOR,
    DEFAULT_CURRENCY_SYMBOL,
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_SETUP_COST,
    DOMAIN,
    SENSOR_PAYBACK_REMAINING,
    SENSOR_SAVINGS_LIFETIME,
    SENSOR_SAVINGS_MONTH,
    SENSOR_SAVINGS_RATE,
    SENSOR_SAVINGS_TODAY,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Savings sensors from a config entry."""
    config = {**entry.data, **entry.options}

    rate = float(config.get(CONF_ELECTRICITY_RATE, DEFAULT_ELECTRICITY_RATE))
    setup_cost = float(config.get(CONF_SETUP_COST, DEFAULT_SETUP_COST))
    currency = config.get(CONF_CURRENCY_SYMBOL, DEFAULT_CURRENCY_SYMBOL)
    power_sensor = config[CONF_SOLAR_POWER_SENSOR]
    today_sensor = config[CONF_SOLAR_ENERGY_TODAY]
    month_sensor = config[CONF_SOLAR_ENERGY_MONTH]

    # Shared storage coordinator
    coordinator = SolarSavingsCoordinator(
        hass=hass,
        entry_id=entry.entry_id,
        rate=rate,
        setup_cost=setup_cost,
        currency=currency,
        power_sensor_id=power_sensor,
        today_sensor_id=today_sensor,
        month_sensor_id=month_sensor,
    )
    await coordinator.async_load()

    entities = [
        SolarSavingsRateSensor(coordinator, entry),
        SolarSavingsTodaySensor(coordinator, entry),
        SolarSavingsMonthSensor(coordinator, entry),
        SolarSavingsLifetimeSensor(coordinator, entry),
        SolarPaybackRemainingSensor(coordinator, entry),
    ]

    async_add_entities(entities)

    # Start listening to source sensors
    await coordinator.async_start(entities)


class SolarSavingsCoordinator:
    """Coordinates data, storage and state tracking for all Solar Savings sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        rate: float,
        setup_cost: float,
        currency: str,
        power_sensor_id: str,
        today_sensor_id: str,
        month_sensor_id: str,
    ) -> None:
        """Initialise coordinator."""
        self.hass = hass
        self.entry_id = entry_id
        self.rate = rate
        self.setup_cost = setup_cost
        self.currency = currency
        self.power_sensor_id = power_sensor_id
        self.today_sensor_id = today_sensor_id
        self.month_sensor_id = month_sensor_id

        # Live values
        self.current_watts: float = 0.0
        self.today_kwh: float = 0.0
        self.month_kwh: float = 0.0
        self.lifetime_kwh: float = 0.0

        # For accumulation tracking
        self._today_peak_kwh: float = 0.0
        self._last_seen_date: date | None = None

        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY + f".{entry_id}")
        self._listeners: list = []
        self._entities: list[SolarSavingsBaseSensor] = []

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load persisted data from storage."""
        data = await self._store.async_load()
        if data:
            self.lifetime_kwh = float(data.get("lifetime_kwh", 0.0))
            self._today_peak_kwh = float(data.get("today_peak_kwh", 0.0))
            date_str = data.get("last_seen_date")
            if date_str:
                try:
                    self._last_seen_date = date.fromisoformat(date_str)
                except ValueError:
                    self._last_seen_date = None
        _LOGGER.debug(
            "Loaded storage: lifetime_kwh=%.3f, today_peak=%.3f, last_seen=%s",
            self.lifetime_kwh,
            self._today_peak_kwh,
            self._last_seen_date,
        )

    async def async_save(self) -> None:
        """Persist data to storage."""
        await self._store.async_save(
            {
                "lifetime_kwh": self.lifetime_kwh,
                "today_peak_kwh": self._today_peak_kwh,
                "last_seen_date": self._last_seen_date.isoformat()
                if self._last_seen_date
                else None,
            }
        )

    # ------------------------------------------------------------------
    # State tracking
    # ------------------------------------------------------------------

    async def async_start(self, entities: list) -> None:
        """Start listening to source sensor state changes."""
        self._entities = entities

        # Read initial states
        self._refresh_power()
        self._refresh_today()
        self._refresh_month()

        # Register listeners
        self._listeners = [
            async_track_state_change_event(
                self.hass,
                [self.power_sensor_id],
                self._handle_power_change,
            ),
            async_track_state_change_event(
                self.hass,
                [self.today_sensor_id],
                self._handle_today_change,
            ),
            async_track_state_change_event(
                self.hass,
                [self.month_sensor_id],
                self._handle_month_change,
            ),
        ]

    def _refresh_power(self) -> None:
        """Read current power sensor state."""
        state = self.hass.states.get(self.power_sensor_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self.current_watts = float(state.state)
            except ValueError:
                pass

    def _refresh_today(self) -> None:
        """Read current today energy sensor state."""
        state = self.hass.states.get(self.today_sensor_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                raw = float(state.state)
                # Normalise to kWh (if sensor reports Wh, convert)
                unit = state.attributes.get("unit_of_measurement", "kWh")
                if unit in ("Wh", "wh"):
                    raw = raw / 1000.0
                self.today_kwh = raw
                self._accumulate_today(raw)
            except ValueError:
                pass

    def _refresh_month(self) -> None:
        """Read current month energy sensor state."""
        state = self.hass.states.get(self.month_sensor_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                raw = float(state.state)
                unit = state.attributes.get("unit_of_measurement", "kWh")
                if unit in ("Wh", "wh"):
                    raw = raw / 1000.0
                self.month_kwh = raw
            except ValueError:
                pass

    def _accumulate_today(self, current_kwh: float) -> None:
        """Accumulate lifetime kWh correctly across day boundaries."""
        today = date.today()

        if self._last_seen_date is None:
            # First run
            self._last_seen_date = today
            self._today_peak_kwh = current_kwh
            return

        if today != self._last_seen_date:
            # It's a new day — commit yesterday's peak to lifetime
            _LOGGER.info(
                "New day detected. Adding %.3f kWh to lifetime total.",
                self._today_peak_kwh,
            )
            self.lifetime_kwh += self._today_peak_kwh
            self._today_peak_kwh = 0.0
            self._last_seen_date = today
            self.hass.async_create_task(self.async_save())

        # Track the highest reading seen today
        if current_kwh > self._today_peak_kwh:
            self._today_peak_kwh = current_kwh
            self.hass.async_create_task(self.async_save())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @callback
    def _handle_power_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ("unknown", "unavailable"):
            try:
                self.current_watts = float(new_state.state)
                self._notify_entities()
            except ValueError:
                pass

    @callback
    def _handle_today_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ("unknown", "unavailable"):
            try:
                raw = float(new_state.state)
                unit = new_state.attributes.get("unit_of_measurement", "kWh")
                if unit in ("Wh", "wh"):
                    raw = raw / 1000.0
                self.today_kwh = raw
                self._accumulate_today(raw)
                self._notify_entities()
            except ValueError:
                pass

    @callback
    def _handle_month_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ("unknown", "unavailable"):
            try:
                raw = float(new_state.state)
                unit = new_state.attributes.get("unit_of_measurement", "kWh")
                if unit in ("Wh", "wh"):
                    raw = raw / 1000.0
                self.month_kwh = raw
                self._notify_entities()
            except ValueError:
                pass

    def _notify_entities(self) -> None:
        """Ask all sensor entities to schedule a state refresh."""
        for entity in self._entities:
            if entity.hass:
                entity.async_schedule_update_ha_state()

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def savings_rate_per_hour(self) -> float:
        """Current savings rate in £/hr based on live watts."""
        kw = self.current_watts / 1000.0
        return kw * self.rate

    @property
    def savings_today(self) -> float:
        """Money saved today (£)."""
        return self.today_kwh * self.rate

    @property
    def savings_month(self) -> float:
        """Money saved this month (£)."""
        return self.month_kwh * self.rate

    @property
    def savings_lifetime(self) -> float:
        """Total lifetime savings (£), including today's so far."""
        return (self.lifetime_kwh + self.today_kwh) * self.rate

    @property
    def payback_remaining(self) -> float:
        """Remaining amount to pay off setup cost (£). Min 0."""
        remaining = self.setup_cost - self.savings_lifetime
        return max(0.0, remaining)

    @property
    def payback_percent(self) -> float:
        """Percentage of setup cost paid off."""
        if self.setup_cost <= 0:
            return 100.0
        pct = (self.savings_lifetime / self.setup_cost) * 100.0
        return min(100.0, round(pct, 2))


# ---------------------------------------------------------------------------
# Sensor entities
# ---------------------------------------------------------------------------


class SolarSavingsBaseSensor(SensorEntity):
    """Base class for Solar Savings sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarSavingsCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Solar Savings",
            "manufacturer": "Solar Savings HA",
            "model": "Solar Savings Tracker",
            "sw_version": "1.0.0",
        }


class SolarSavingsRateSensor(SolarSavingsBaseSensor):
    """Sensor: current savings rate (£/hr)."""

    _attr_icon = "mdi:lightning-bolt"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Current Savings Rate"

    def __init__(self, coordinator: SolarSavingsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_SAVINGS_RATE)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.savings_rate_per_hour, 4)

    @property
    def native_unit_of_measurement(self) -> str:
        return f"{self._coordinator.currency}/hr"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._coordinator
        return {
            "current_watts": c.current_watts,
            "current_kw": round(c.current_watts / 1000, 3),
            "rate_per_kwh": c.rate,
            "currency": c.currency,
            "rate_per_second": round(c.savings_rate_per_hour / 3600, 8),
            "setup_cost": c.setup_cost,
        }


class SolarSavingsTodaySensor(SolarSavingsBaseSensor):
    """Sensor: today's total savings (£)."""

    _attr_icon = "mdi:calendar-today"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_name = "Savings Today"

    def __init__(self, coordinator: SolarSavingsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_SAVINGS_TODAY)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.savings_today, 4)

    @property
    def native_unit_of_measurement(self) -> str:
        return self._coordinator.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._coordinator
        return {
            "today_kwh": round(c.today_kwh, 3),
            "rate_per_kwh": c.rate,
        }


class SolarSavingsMonthSensor(SolarSavingsBaseSensor):
    """Sensor: this month's total savings (£)."""

    _attr_icon = "mdi:calendar-month"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_name = "Savings This Month"

    def __init__(self, coordinator: SolarSavingsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_SAVINGS_MONTH)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.savings_month, 4)

    @property
    def native_unit_of_measurement(self) -> str:
        return self._coordinator.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._coordinator
        return {
            "month_kwh": round(c.month_kwh, 3),
            "rate_per_kwh": c.rate,
        }


class SolarSavingsLifetimeSensor(SolarSavingsBaseSensor):
    """Sensor: total lifetime savings (£)."""

    _attr_icon = "mdi:piggy-bank"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_name = "Total Lifetime Savings"

    def __init__(self, coordinator: SolarSavingsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_SAVINGS_LIFETIME)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.savings_lifetime, 4)

    @property
    def native_unit_of_measurement(self) -> str:
        return self._coordinator.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._coordinator
        return {
            "lifetime_kwh": round(c.lifetime_kwh, 3),
            "today_kwh_included": round(c.today_kwh, 3),
            "payback_percent": c.payback_percent,
            "setup_cost": c.setup_cost,
        }


class SolarPaybackRemainingSensor(SolarSavingsBaseSensor):
    """Sensor: remaining amount to pay off setup cost (£)."""

    _attr_icon = "mdi:cash-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Payback Remaining"

    def __init__(self, coordinator: SolarSavingsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_PAYBACK_REMAINING)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.payback_remaining, 4)

    @property
    def native_unit_of_measurement(self) -> str:
        return self._coordinator.currency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._coordinator
        return {
            "setup_cost": c.setup_cost,
            "lifetime_savings": round(c.savings_lifetime, 4),
            "payback_percent": c.payback_percent,
            "savings_rate_per_hour": round(c.savings_rate_per_hour, 4),
            "currency": c.currency,
        }
