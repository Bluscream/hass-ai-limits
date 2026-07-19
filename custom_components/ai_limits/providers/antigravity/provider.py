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
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    PROVIDER_ANTIGRAVITY,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ...models import LimitsData, OAuthTokens
from .. import oauth
from ..base import AIProvider
from ..codeassist_models import LoadCodeAssistResponse, apply_credits
from . import oauth as ag_oauth
from .models import FetchAvailableModelsResponse, onboard_project

CLOUDCODE = "https://cloudcode-pa.googleapis.com/v1internal"
# fetchAvailableModels / onboardUser are served from the "daily" host.
DAILY = "https://daily-cloudcode-pa.googleapis.com/v1internal"

# REQUIRED: Google gates fetchAvailableModels (and the credits array on
# loadCodeAssist) on this client User-Agent. Without it the API returns
# 403 PERMISSION_DENIED even with a fully-scoped token.
USER_AGENT = "antigravity/2.1.1 windows/amd64 google-api-nodejs-client/10.3.0"

_LOGGER = logging.getLogger(__name__)


class AntigravityProvider(AIProvider):
    provider_id = PROVIDER_ANTIGRAVITY
    label = "Google AI (Code Assist - Gemini, Claude, GPT)"
    manufacturer = "Google (Antigravity Code Assist)"

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
        tokens = await oauth.async_refresh(
            self.hass, ag_oauth.CLIENT, d[CONF_REFRESH_TOKEN]
        )
        self.hass.config_entries.async_update_entry(
            self.entry, data={**d, **tokens.to_storage()}
        )
        return tokens.access_token

    async def async_fetch(self) -> LimitsData:
        try:
            token = await self._token()
        except oauth.OAuthError as err:
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
