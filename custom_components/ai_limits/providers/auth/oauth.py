"""Generic OAuth 2.0 auth helper, encapsulated in a single AuthProvider."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ...models import OAuthTokens
from .base import AuthProvider

_LOGGER = logging.getLogger(__name__)


class OAuthError(Exception):
    """Raised when an OAuth step fails."""


class OAuthProvider(AuthProvider):
    """AuthProvider that handles OAuth token lifetime, refresh, and PKCE exchange for any provider."""

    auth_type_id = "oauth"

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        super().__init__(hass)
        self.auth_url = config["auth_url"]
        self.token_url = config["token_url"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.redirect_uri = config["redirect_uri"]
        self.scopes = config["scopes"]
        self.use_pkce = config.get("use_pkce", False)

    def new_state(self) -> str:
        return secrets.token_hex(16)

    def generate_pkce(self) -> tuple[str, str]:
        verifier = self._b64url(secrets.token_bytes(32))
        challenge = self._b64url(hashlib.sha256(verifier.encode()).digest())
        return verifier, challenge

    def _b64url(self, raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def build_authorize_url(self, state: str, challenge: str | None = None) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
        }
        # Some OAuth providers expect offline access or consent prompts
        if "google.com" in self.auth_url:
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif "discord.com" in self.auth_url:
            pass

        if self.use_pkce and challenge:
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        return f"{self.auth_url}?{urlencode(params)}"

    def extract_code(self, pasted: str) -> str | None:
        pasted = pasted.strip()
        if pasted.startswith("http"):
            return parse_qs(urlparse(pasted).query).get("code", [None])[0]
        return pasted or None

    async def async_exchange_code(self, code: str, verifier: str | None = None) -> OAuthTokens:
        body = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        if self.use_pkce and verifier:
            body["code_verifier"] = verifier

        headers = {"Accept": "application/json"}
        # Discord expects x-www-form-urlencoded
        if "discord.com" in self.token_url:
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        return await self._post_token(body, headers)

    async def async_refresh(self, refresh_token: str) -> OAuthTokens:
        body = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        headers = {"Accept": "application/json"}
        if "discord.com" in self.token_url:
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        tokens = await self._post_token(body, headers)
        if not tokens.refresh_token:
            tokens.refresh_token = refresh_token
        return tokens

    async def _post_token(self, body: dict, headers: dict) -> OAuthTokens:
        session = async_get_clientsession(self.hass)
        try:
            resp = await session.post(self.token_url, data=body, headers=headers)
        except ClientError as err:
            raise OAuthError(f"connection: {err}") from err
        if resp.status != 200:
            text = await resp.text()
            raise OAuthError(f"token request failed ({resp.status}): {text[:200]}")
        return OAuthTokens.from_response(await resp.json())
