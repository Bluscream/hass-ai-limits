"""Provider registry.

To add a new provider: create a subpackage exposing an AIProvider subclass,
import it here, and add it to ``_ALL``. The config flow, coordinator and menu
all read from the registry, so nothing else needs touching.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import CONF_PROVIDER
from .antigravity import AntigravityProvider
from .base import AIProvider, AuthError, CannotConnect
from .claude import ClaudeWebProvider
from .gemini import GeminiProvider

_ALL: list[type[AIProvider]] = [
    ClaudeWebProvider,
    AntigravityProvider,
    GeminiProvider,
]

REGISTRY: dict[str, type[AIProvider]] = {p.provider_id: p for p in _ALL}


def get_provider(hass: HomeAssistant, entry: ConfigEntry) -> AIProvider:
    cls = REGISTRY.get(entry.data[CONF_PROVIDER])
    if cls is None:
        raise ValueError(f"Unknown provider: {entry.data[CONF_PROVIDER]}")
    return cls(hass, entry)


def menu_options() -> dict[str, str]:
    """provider_id -> label, for the add-integration menu (visible only)."""
    return {p.provider_id: p.label for p in _ALL if p.menu_visible}


__all__ = [
    "AIProvider",
    "AuthError",
    "CannotConnect",
    "REGISTRY",
    "get_provider",
    "menu_options",
]
