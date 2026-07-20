"""AI Limit tracker registry."""

from __future__ import annotations

from .antigravity import AntigravityProvider
from .base import AIProvider, AuthError, CannotConnect
from .claude import ClaudeWebProvider
from .devin import DevinProvider
from .gemini import GeminiProvider
from .claude_api.provider import ClaudeAPIProvider
from .deepseek.provider import DeepSeekAPIProvider
from .openrouter.provider import OpenRouterAPIProvider

_ALL: list[type[AIProvider]] = [
    ClaudeWebProvider,
    ClaudeAPIProvider,
    DevinProvider,
    DeepSeekAPIProvider,
    OpenRouterAPIProvider,
    AntigravityProvider,
    GeminiProvider,
]

REGISTRY: dict[str, type[AIProvider]] = {p.provider_id: p for p in _ALL}


def menu_options() -> dict[str, str]:
    """provider_id -> label, for the add-integration menu (visible only)."""
    return {p.provider_id: p.label for p in _ALL if p.menu_visible}
