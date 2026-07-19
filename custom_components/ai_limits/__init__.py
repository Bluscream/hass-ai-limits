"""The AI Limits integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PROVIDER, PLATFORMS
from .coordinator import AILimitsCoordinator

_LOGGER = logging.getLogger(__name__)

type AILimitsConfigEntry = ConfigEntry[AILimitsCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> bool:
    """Set up AI Limits from a config entry."""
    _LOGGER.info(
        "Setting up AI Limits account '%s' (provider=%s)",
        entry.title,
        entry.data.get(CONF_PROVIDER),
    )
    coordinator = AILimitsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading AI Limits account '%s'", entry.title)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: AILimitsConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
