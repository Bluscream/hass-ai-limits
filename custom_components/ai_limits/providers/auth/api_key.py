"""API Key authentication provider."""

from __future__ import annotations

from .base import AuthProvider


class ApiKeyAuthProvider(AuthProvider):
    """AuthProvider representing simple developer/API token based authentication."""

    auth_type_id = "api_key"
