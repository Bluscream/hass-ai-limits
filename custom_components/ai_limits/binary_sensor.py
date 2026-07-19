"""Binary sensor for AI Limits."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AILimitsConfigEntry
from .const import STATUS_RATE_LIMITED
from .entity import AILimitsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AILimitsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rate-limited binary sensor."""
    async_add_entities([RateLimitedBinarySensor(entry.runtime_data)])


class RateLimitedBinarySensor(AILimitsEntity, BinarySensorEntity):
    """On when any usage window is at its limit.

    Redundant with the Status sensor (== 'rate_limited'); disabled by default
    as a convenience boolean for automations. Enable it in the entity settings.
    """

    _attr_name = "Rate limited"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rate_limited")

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        if data.status == STATUS_RATE_LIMITED:
            return True
        return any(
            win.status not in (None, "within_limit")
            for win in data.windows.values()
        )
