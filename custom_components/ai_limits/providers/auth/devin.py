"""Devin specific authentication provider."""

from __future__ import annotations

from .base import AuthProvider


class DevinAuthProvider(AuthProvider):
    """AuthProvider representing Devin's custom Bearer token + Org ID credentials."""

    auth_type_id = "devin"
