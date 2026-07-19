"""Data update coordinator for AI Limits."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_PROVIDER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .models import LimitsData
from .providers import get_provider

_LOGGER = logging.getLogger(__name__)


class AILimitsCoordinator(DataUpdateCoordinator[LimitsData]):
    """Polls one AI account for its current limits."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.provider_id: str = entry.data[CONF_PROVIDER]
        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._provider = get_provider(hass, entry)
        self.manufacturer: str = self._provider.manufacturer
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=timedelta(seconds=scan),
        )

    async def _async_update_data(self) -> LimitsData:
        # Providers encode failures in the returned data rather than raising,
        # so a transient error still updates the status entity.
        return await self._provider.async_fetch()
