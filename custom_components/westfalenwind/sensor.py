from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WestfalenwindCoordinator, WestfalenwindDynamicCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet den Sensor fuer den Config Entry ein."""
    coordinator: WestfalenwindCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    dynamic_coordinator: WestfalenwindDynamicCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["dynamic_coordinator"]
    async_add_entities(
        [
            WestfalenwindSensor(coordinator),
            WestfalenwindForecastSensor(coordinator),
            WestfalenwindDynamicSensor(dynamic_coordinator),
            WestfalenwindDynamicForecastSensor(dynamic_coordinator),
        ]
    )


class WestfalenwindSensor(CoordinatorEntity[WestfalenwindCoordinator], SensorEntity):
    """Sensor fuer den aktuell gueltigen Westfalenwind-Strompreis."""

    _attr_name = "Westfalenwind Strompreis"
    _attr_unique_id = "westfalenwind_current_price"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    # MONETARY wird absichtlich nicht gesetzt, da ct/kWh keine reine Waehrung ist.

    @property
    def native_value(self) -> float | None:
        """Liefert den aktuellen Preis in ct/kWh."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert Zusatzdaten zum aktuell gueltigen Preisintervall."""
        return {
            "tariff_name": self.coordinator.current_tariff_name,
            "valid_from": self.coordinator.current_valid_from,
            "valid_until": self.coordinator.current_valid_until,
            "refresh_schedule": self.coordinator.refresh_schedule,
        }


class WestfalenwindForecastSensor(
    CoordinatorEntity[WestfalenwindCoordinator], SensorEntity
):
    """Sensor mit den geladenen Forecast-Daten des Standardtarifs."""

    _attr_name = "Westfalenwind Strompreis Forecast"
    _attr_unique_id = "westfalenwind_price_forecast"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> float | None:
        """Liefert den Preis des naechsten Intervalls als kompakten Forecast-Wert."""
        now = self.coordinator.current_valid_until
        if now is None:
            return None

        for entry in self.coordinator.forecast:
            if entry.get("start") == now:
                price = entry.get("price_ct_kwh")
                return price if isinstance(price, float) else None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert den kompletten geladenen Forecast-Datensatz."""
        return {
            "forecast": self.coordinator.forecast,
            "entries": len(self.coordinator.forecast),
            "refresh_schedule": self.coordinator.refresh_schedule,
        }


class WestfalenwindDynamicSensor(
    CoordinatorEntity[WestfalenwindDynamicCoordinator], SensorEntity
):
    """Sensor fuer den voll dynamischen Westfalenwind-Strompreis."""

    _attr_name = "Westfalenwind Dynamischer Strompreis"
    _attr_unique_id = "westfalenwind_dynamic_price"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        """Liefert den aktuellen dynamischen Preis in ct/kWh."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert Zusatzdaten zum aktuell gueltigen dynamischen Preisintervall."""
        return {
            "tariff_name": self.coordinator.current_tariff_name,
            "valid_from": self.coordinator.current_valid_from,
            "valid_until": self.coordinator.current_valid_until,
            "refresh_schedule": self.coordinator.refresh_schedule,
        }


class WestfalenwindDynamicForecastSensor(
    CoordinatorEntity[WestfalenwindDynamicCoordinator], SensorEntity
):
    """Sensor mit den geladenen Forecast-Daten des dynamischen Tarifs."""

    _attr_name = "Westfalenwind Dynamischer Strompreis Forecast"
    _attr_unique_id = "westfalenwind_dynamic_price_forecast"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> float | None:
        """Liefert den Preis des naechsten Intervalls als kompakten Forecast-Wert."""
        now = self.coordinator.current_valid_until
        if now is None:
            return None

        for entry in self.coordinator.forecast:
            if entry.get("start") == now:
                price = entry.get("price_ct_kwh")
                return price if isinstance(price, float) else None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert den kompletten geladenen Forecast-Datensatz."""
        return {
            "forecast": self.coordinator.forecast,
            "entries": len(self.coordinator.forecast),
            "refresh_schedule": self.coordinator.refresh_schedule,
        }
