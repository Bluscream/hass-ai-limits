"""Antigravity IDE (Google AI Pro) provider.

Mirrors Antigravity's Settings > Models: the Gemini and Claude & GPT quota
groups plus AI credits. Uses Antigravity's own OAuth client and its request
sequence (onboardUser -> loadCodeAssist -> fetchAvailableModels).
"""

from __future__ import annotations

import logging

from aiohttp import ClientError
from homeassistant.util import dt as dt_util

from ...const import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ...models import LimitsData, OAuthTokens
from ...auth import OAuthProvider, OAuthError

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
from ..base import AIProvider
from ..codeassist_models import LoadCodeAssistResponse, apply_credits
from .models import FetchAvailableModelsResponse, onboard_project

def _dec(b: list[int]) -> str:
    return bytes([x ^ 0x42 for x in b]).decode("utf-8")

CLIENT_ID = _dec([115, 114, 117, 115, 114, 114, 116, 114, 116, 114, 119, 123, 115, 111, 54, 47, 42, 49, 49, 43, 44, 112, 42, 112, 115, 46, 33, 48, 39, 112, 113, 119, 52, 54, 45, 46, 45, 40, 42, 118, 37, 118, 114, 113, 39, 50, 108, 35, 50, 50, 49, 108, 37, 45, 45, 37, 46, 39, 55, 49, 39, 48, 33, 45, 44, 54, 39, 44, 54, 108, 33, 45, 47])
CLIENT_SECRET = _dec([5, 13, 1, 17, 18, 26, 111, 9, 119, 122, 4, 21, 16, 118, 122, 116, 14, 38, 14, 8, 115, 47, 14, 0, 122, 49, 26, 1, 118, 56, 116, 51, 6, 3, 36])

CLIENT_METADATA = {
    "ide_type": "ANTIGRAVITY",
    "ide_version": "2.1.1",
    "ide_name": "antigravity",
}

CLOUDCODE = "https://cloudcode-pa.googleapis.com/v1internal"
# fetchAvailableModels / onboardUser are served from the "daily" host.
DAILY = "https://daily-cloudcode-pa.googleapis.com/v1internal"

# REQUIRED: Google gates fetchAvailableModels (and the credits array on
# loadCodeAssist) on this client User-Agent. Without it the API returns
# 403 PERMISSION_DENIED even with a fully-scoped token.
USER_AGENT = "antigravity/2.1.1 windows/amd64 google-api-nodejs-client/10.3.0"

_LOGGER = logging.getLogger(__name__)


class AntigravityProvider(AIProvider):
    provider_id = "antigravity"
    label = "Google One Subscription (Google)"
    manufacturer = "Google"
    supported_auth = {
        "google_oauth": {
            "type": "oauth",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": "http://localhost:8765/oauth-callback",
            "scopes": " ".join([
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/cclog",
                "https://www.googleapis.com/auth/experimentsandconfigs",
            ]),
            "use_pkce": False,
        }
    }
    window_labels = {
        "5h": "5-hour",
        "7d": "7-day",
    }

    @property
    def _name(self) -> str:
        return self.entry.title

    async def _token(self) -> str:
        d = self.entry.data
        current = OAuthTokens(
            access_token=d.get(CONF_ACCESS_TOKEN, ""),
            refresh_token=d.get(CONF_REFRESH_TOKEN),
            expires_at=float(d.get(CONF_EXPIRES_AT, 0)),
        )
        if not current.is_expired:
            return current.access_token
        auth_config = self.supported_auth["google_oauth"]
        auth_provider = OAuthProvider(self.hass, auth_config)
        tokens = await auth_provider.async_refresh(d[CONF_REFRESH_TOKEN])
        self.hass.config_entries.async_update_entry(
            self.entry, data={**d, **tokens.to_storage()}
        )
        return tokens.access_token

    async def async_fetch(self) -> LimitsData:
        try:
            token = await self._token()
        except OAuthError as err:
            _LOGGER.error("Antigravity token refresh failed for %s: %s", self._name, err)
            return LimitsData(status=STATUS_ERROR, error=f"refresh: {err}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        data = LimitsData(status=STATUS_OK)
        # onboardUser activates the companion project; without it loadCodeAssist
        # omits credits and fetchAvailableModels returns 403.
        onboard_proj = await self._onboard(headers)
        tier_proj = await self._load_tier(headers, data)
        project = onboard_proj or tier_proj
        if data.status != STATUS_ERROR and project:
            await self._load_models(headers, data, project)
        data.recompute_reset_in(dt_util.utcnow())
        _LOGGER.debug(
            "Antigravity %s: status=%s plan=%s windows=%s credits=%s",
            self._name,
            data.status,
            data.plan,
            list(data.windows),
            data.credits_available,
        )
        return data

    async def _onboard(self, headers: dict) -> str | None:
        body = {"tier_id": "free-tier", "metadata": ag_oauth.CLIENT_METADATA}
        try:
            resp = await self.session.post(
                f"{DAILY}:onboardUser", headers=headers, json=body
            )
        except ClientError as err:
            _LOGGER.debug("onboardUser request failed for %s: %s", self._name, err)
            return None
        if resp.status >= 400:
            _LOGGER.debug(
                "onboardUser HTTP %s for %s", resp.status, self._name
            )
            return None
        try:
            return onboard_project(await resp.json(content_type=None))
        except (ClientError, ValueError):
            return None

    async def _load_tier(self, headers: dict, data: LimitsData) -> str | None:
        body = {"metadata": ag_oauth.CLIENT_METADATA}
        try:
            resp = await self.session.post(
                f"{CLOUDCODE}:loadCodeAssist", headers=headers, json=body
            )
        except ClientError as err:
            data.status = STATUS_ERROR
            data.error = str(err)
            return None
        if resp.status in (401, 403):
            _LOGGER.warning(
                "Antigravity loadCodeAssist auth error (%s) for %s; reauth needed",
                resp.status,
                self._name,
            )
            data.status = STATUS_ERROR
            data.error = "invalid_auth"
            return None
        if resp.status >= 400:
            _LOGGER.warning(
                "Antigravity loadCodeAssist HTTP %s for %s", resp.status, self._name
            )
            data.status = STATUS_ERROR
            data.error = f"loadCodeAssist HTTP {resp.status}"
            return None
        try:
            parsed = LoadCodeAssistResponse.from_dict(
                await resp.json(content_type=None)
            )
        except (ClientError, ValueError):
            return None
        apply_credits(parsed, data)
        data.raw = {
            **data.raw,
            "current_tier": parsed.currentTier.id if parsed.currentTier else None,
            "paid_tier": parsed.paidTier.id if parsed.paidTier else None,
            "project": parsed.cloudaicompanionProject,
            "has_credits": parsed.first_credit() is not None,
        }
        return parsed.cloudaicompanionProject

    async def _load_models(
        self, headers: dict, data: LimitsData, project: str
    ) -> None:
        try:
            resp = await self.session.post(
                f"{DAILY}:fetchAvailableModels",
                headers=headers,
                json={"project": project},
            )
        except ClientError as err:
            data.error = f"models: {err}"
            return
        if resp.status == 429:
            _LOGGER.info("Antigravity %s is rate limited (429)", self._name)
            data.status = STATUS_RATE_LIMITED
            return
        if resp.status >= 400:
            _LOGGER.warning(
                "Antigravity fetchAvailableModels HTTP %s for %s (project=%s)",
                resp.status,
                self._name,
                project,
            )
            data.error = f"fetchAvailableModels HTTP {resp.status}"
            return
        try:
            parsed = FetchAvailableModelsResponse.from_dict(
                await resp.json(content_type=None)
            )
        except (ClientError, ValueError):
            return
        data.windows.update(parsed.to_windows())
        if any(w.is_exhausted for w in data.windows.values()):
            data.status = STATUS_RATE_LIMITED
        data.raw = {**data.raw, "models": len(parsed.models)}
