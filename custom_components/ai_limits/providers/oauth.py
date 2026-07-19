"""Generic Google OAuth 2.0 code flow, shared by the Code Assist providers.

Each provider supplies an OAuthClient (client id/secret, redirect, scopes,
whether to use PKCE); this module builds the authorize URL and does the token
exchange / refresh. Uses a manual paste flow (no loopback listener): the user
authorises and pastes back the redirect URL or the bare code.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import OAuthTokens

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class OAuthError(Exception):
    """Raised when an OAuth step fails."""


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str  # space-separated
    use_pkce: bool = False


def new_state() -> str:
    return secrets.token_hex(16)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def build_authorize_url(
    client: OAuthClient, state: str, challenge: str | None = None
) -> str:
    params = {
        "client_id": client.client_id,
        "response_type": "code",
        "redirect_uri": client.redirect_uri,
        "scope": client.scopes,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    if client.use_pkce and challenge:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    return f"{AUTH_URL}?{urlencode(params)}"


def extract_code(pasted: str) -> str | None:
    """Accept either a bare code or the full redirected URL."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        return parse_qs(urlparse(pasted).query).get("code", [None])[0]
    return pasted or None


async def async_exchange_code(
    hass: HomeAssistant, client: OAuthClient, code: str, verifier: str | None = None
) -> OAuthTokens:
    body = {
        "code": code,
        "client_id": client.client_id,
        "client_secret": client.client_secret,
        "redirect_uri": client.redirect_uri,
        "grant_type": "authorization_code",
    }
    if client.use_pkce and verifier:
        body["code_verifier"] = verifier
    return await _post_token(hass, body)


async def async_refresh(
    hass: HomeAssistant, client: OAuthClient, refresh_token: str
) -> OAuthTokens:
    body = {
        "client_id": client.client_id,
        "client_secret": client.client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    tokens = await _post_token(hass, body)
    if not tokens.refresh_token:
        tokens.refresh_token = refresh_token
    return tokens


async def _post_token(hass: HomeAssistant, body: dict) -> OAuthTokens:
    session = async_get_clientsession(hass)
    try:
        resp = await session.post(TOKEN_URL, data=body)
    except ClientError as err:
        raise OAuthError(f"connection: {err}") from err
    if resp.status != 200:
        text = await resp.text()
        raise OAuthError(f"token request failed ({resp.status}): {text[:200]}")
    return OAuthTokens.from_response(await resp.json())
