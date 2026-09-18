"""Auth registry containing all supported authentication mechanisms."""

from __future__ import annotations

from .api_key import ApiKeyAuthProvider
from .base import AuthProvider
from .cookie import CookieAuthProvider
from .devin import DevinAuthProvider
from .oauth import OAuthError, OAuthProvider

__all__ = [
    "ApiKeyAuthProvider",
    "AuthProvider",
    "CookieAuthProvider",
    "DevinAuthProvider",
    "OAuthError",
    "OAuthProvider",
]
