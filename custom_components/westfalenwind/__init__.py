from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import WestfalenwindSmartCoordinator, WestfalenwindFlexCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet einen Config Entry der Integration ein."""
    coordinator = WestfalenwindSmartCoordinator(hass, dict(entry.options))
    dynamic_coordinator = WestfalenwindFlexCoordinator(hass, dict(entry.options))
    await coordinator.async_config_entry_first_refresh()
    await dynamic_coordinator.async_config_entry_first_refresh()

    update_listener = entry.add_update_listener(_async_update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "dynamic_coordinator": dynamic_coordinator,
        "update_listener": update_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlaedt einen Config Entry der Integration."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data["update_listener"]()

    coordinator: WestfalenwindSmartCoordinator = entry_data["coordinator"]
    dynamic_coordinator: WestfalenwindFlexCoordinator = entry_data[
        "dynamic_coordinator"
    ]
    await coordinator.async_shutdown()
    await dynamic_coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Laedt den Config Entry neu, wenn Optionen geaendert wurden."""
    await hass.config_entries.async_reload(entry.entry_id)
