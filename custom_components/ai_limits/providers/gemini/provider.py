"""Gemini CLI Code Assist provider (standard-tier, Gemini-only).

Independent gemini-cli OAuth login. Reads per-model quota via retrieveUserQuota.
"""

from __future__ import annotations

import logging

from aiohttp import ClientError
from homeassistant.util import dt as dt_util

from ...const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_GCP_PROJECT,
    CONF_REFRESH_TOKEN,
    PROVIDER_GOOGLE_CA,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ...models import LimitsData, OAuthTokens
from .. import oauth
from ..base import AIProvider
from ..codeassist_models import (
    ClientMetadata,
    LoadCodeAssistRequest,
    LoadCodeAssistResponse,
    apply_credits,
)
from . import oauth as gm_oauth
from .models import RetrieveUserQuotaRequest, RetrieveUserQuotaResponse

CLOUDCODE = "https://cloudcode-pa.googleapis.com/v1internal"

_LOGGER = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    # Deprecated: superseded by the Antigravity provider, which returns the
    # same Code Assist quota plus Claude/GPT + credits. Kept registered so
    # existing entries keep working; hidden from the add menu.
    provider_id = PROVIDER_GOOGLE_CA
    label = "Google Gemini Code Assist (deprecated)"
    manufacturer = "Google (Gemini Code Assist)"
    menu_visible = False

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
            self.hass, gm_oauth.CLIENT, d[CONF_REFRESH_TOKEN]
        )
        self.hass.config_entries.async_update_entry(
            self.entry, data={**d, **tokens.to_storage()}
        )
        return tokens.access_token

    async def async_fetch(self) -> LimitsData:
        try:
            token = await self._token()
        except oauth.OAuthError as err:
            _LOGGER.error(
                "Gemini token refresh failed for %s: %s", self.entry.title, err
            )
            return LimitsData(status=STATUS_ERROR, error=f"refresh: {err}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        data = LimitsData(status=STATUS_OK)
        await self._load_tier(headers, data)
        if data.status != STATUS_ERROR:
            await self._load_quota(headers, data)
        data.recompute_reset_in(dt_util.utcnow())
        _LOGGER.debug(
            "Gemini %s: status=%s plan=%s windows=%s",
            self.entry.title,
            data.status,
            data.plan,
            list(data.windows),
        )
        return data

    async def _load_tier(self, headers: dict, data: LimitsData) -> None:
        request = LoadCodeAssistRequest(
            metadata=ClientMetadata(gm_oauth.CLIENT_METADATA)
        )
        try:
            resp = await self.session.post(
                f"{CLOUDCODE}:loadCodeAssist", headers=headers, json=request.to_dict()
            )
        except ClientError as err:
            data.status = STATUS_ERROR
            data.error = str(err)
            return
        if resp.status == 429:
            data.status = STATUS_RATE_LIMITED
            return
        if resp.status in (401, 403):
            _LOGGER.warning(
                "Gemini loadCodeAssist auth error (%s) for %s; reauth needed",
                resp.status,
                self.entry.title,
            )
            data.status = STATUS_ERROR
            data.error = "invalid_auth"
            return
        if resp.status >= 400:
            _LOGGER.warning(
                "Gemini loadCodeAssist HTTP %s for %s", resp.status, self.entry.title
            )
            data.status = STATUS_ERROR
            data.error = f"loadCodeAssist HTTP {resp.status}"
            return
        try:
            parsed = LoadCodeAssistResponse.from_dict(
                await resp.json(content_type=None)
            )
        except (ClientError, ValueError):
            return
        apply_credits(parsed, data)
        if parsed.cloudaicompanionProject and (
            self.entry.data.get(CONF_GCP_PROJECT) != parsed.cloudaicompanionProject
        ):
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={
                    **self.entry.data,
                    CONF_GCP_PROJECT: parsed.cloudaicompanionProject,
                },
            )

    async def _load_quota(self, headers: dict, data: LimitsData) -> None:
        request = RetrieveUserQuotaRequest(
            project=self.entry.data.get(CONF_GCP_PROJECT)
        )
        try:
            resp = await self.session.post(
                f"{CLOUDCODE}:retrieveUserQuota",
                headers=headers,
                json=request.to_dict(),
            )
        except ClientError as err:
            data.error = f"quota: {err}"
            return
        if resp.status == 429:
            data.status = STATUS_RATE_LIMITED
            return
        if resp.status >= 400:
            data.error = f"retrieveUserQuota HTTP {resp.status}"
            return
        try:
            parsed = RetrieveUserQuotaResponse.from_dict(
                await resp.json(content_type=None)
            )
        except (ClientError, ValueError):
            return
        data.windows.update(parsed.to_windows())
        data.raw = {**data.raw, "buckets": len(parsed.buckets)}
