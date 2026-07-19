"""Providers module facade. Exposes AI registries and subpackages."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ai import REGISTRY, AIProvider, AuthError, CannotConnect, menu_options


def get_provider(hass: HomeAssistant, entry: ConfigEntry) -> AIProvider:
    """Instantiate the correct AIProvider subclass for *entry*."""
    from .ai.base import CannotConnect as _CannotConnect  # noqa: F401 – re-export guard
    provider_id: str = entry.data.get("provider", "")
    cls = REGISTRY.get(provider_id)
    if cls is None:
        raise _CannotConnect(f"Unknown provider: {provider_id!r}")
    return cls(hass, entry)
