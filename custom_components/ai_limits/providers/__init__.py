"""Providers module facade. Exposes AI registries and subpackages."""

from __future__ import annotations

from .ai import REGISTRY, AIProvider, AuthError, CannotConnect, menu_options
