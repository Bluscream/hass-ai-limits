"""Antigravity IDE (Google AI Pro) provider."""

from .oauth import CLIENT, CLIENT_METADATA
from .provider import AntigravityProvider

__all__ = ["AntigravityProvider", "CLIENT", "CLIENT_METADATA"]
