"""Cookie/Session authentication provider."""

from __future__ import annotations

from .base import AuthProvider


class CookieAuthProvider(AuthProvider):
    """AuthProvider representing cookie-based web session authentication."""

    auth_type_id = "cookie"
