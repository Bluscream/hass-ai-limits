"""Base class for authentication providers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


class AuthProvider:
    """Base class for authentication mechanism helper classes."""

    auth_type_id: str = ""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
