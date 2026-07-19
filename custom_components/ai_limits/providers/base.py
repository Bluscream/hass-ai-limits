"""Base class every AI provider inherits."""

from __future__ import annotations

from abc import ABC, abstractmethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import LimitsData


class AuthError(Exception):
    """Raised when credentials are rejected."""


class CannotConnect(Exception):
    """Raised when the provider endpoint is unreachable / blocked."""


class AIProvider(ABC):
    """One configured account for one AI service.

    Subclasses set ``provider_id`` (stored in the config entry) and ``label``
    (shown in the add-integration menu), and implement ``async_fetch``.
    """

    provider_id: str = ""
    label: str = ""
    manufacturer: str = "AI"  # shown as the device manufacturer
    # Whether to offer this provider in the add-integration menu. Deprecated
    # providers stay registered (so existing entries load) but hidden.
    menu_visible: bool = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.session = async_get_clientsession(hass)

    @abstractmethod
    async def async_fetch(self) -> LimitsData:
        """Return the current limits snapshot. Encode failures in status."""

    # Convenience for entities/coordinator.
    @property
    def title_prefix(self) -> str:
        return self.label
