from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WestfalenwindSmartCoordinator, WestfalenwindFlexCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet den Sensor fuer den Config Entry ein."""
    coordinator: WestfalenwindSmartCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    dynamic_coordinator: WestfalenwindFlexCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["dynamic_coordinator"]
    async_add_entities(
        [
            WestfalenwindSmartForecastSensor(coordinator),
            WestfalenwindFlexForecastSensor(dynamic_coordinator),
        ]
    )


class WestfalenwindSmartForecastSensor(
    CoordinatorEntity[WestfalenwindSmartCoordinator], SensorEntity
):
    """Forecast-Sensor fuer den Tarif WWS Hochstift Smart."""

    _attr_name = "WestfalenWind Smart Strompreis"
    _attr_unique_id = "westfalenwind_price_forecast"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> float | None:
        """Liefert den aktuell gueltigen Preis in ct/kWh."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert den kompletten geladenen Forecast-Datensatz."""
        return {
            "forecast": self.coordinator.forecast,
            "entries": len(self.coordinator.forecast),
            "refresh_schedule": self.coordinator.refresh_schedule,
        }


class WestfalenwindFlexForecastSensor(
    CoordinatorEntity[WestfalenwindFlexCoordinator], SensorEntity
):
    """Forecast-Sensor fuer den Tarif WWS Hochstift Flex."""

    _attr_name = "WestfalenWind Flex Strompreis"
    _attr_unique_id = "westfalenwind_dynamic_price_forecast"
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> float | None:
        """Liefert den aktuell gueltigen Preis in ct/kWh."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert den kompletten geladenen Forecast-Datensatz."""
        return {
            "forecast": self.coordinator.forecast,
            "entries": len(self.coordinator.forecast),
            "refresh_schedule": self.coordinator.refresh_schedule,
        }
