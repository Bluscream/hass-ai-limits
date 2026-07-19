"""Gemini CLI Code Assist provider."""

from .oauth import CLIENT
from .provider import GeminiProvider

__all__ = ["GeminiProvider", "CLIENT"]
