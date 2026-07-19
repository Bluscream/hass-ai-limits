"""Shared entity base for AI Limits."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACCOUNT_NAME, DOMAIN
from .coordinator import AILimitsCoordinator


class AILimitsEntity(CoordinatorEntity[AILimitsCoordinator]):
    """Base entity that ties to the account device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AILimitsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=coordinator.manufacturer,
            model=entry.data.get(CONF_ACCOUNT_NAME),
        )
