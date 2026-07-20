"""Gemini CLI Code Assist provider (standard-tier, Gemini-only).

Independent gemini-cli OAuth login. Reads per-model quota via retrieveUserQuota.
"""

from __future__ import annotations

import logging

from aiohttp import ClientError
from homeassistant.util import dt as dt_util

from ....const import (
    CONF_GCP_PROJECT,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ....models import LimitsData, OAuthTokens
from ...auth import OAuthProvider, OAuthError
from ..base import AIProvider, deobfuscate
from ..codeassist_models import (
    ClientMetadata,
    LoadCodeAssistRequest,
    LoadCodeAssistResponse,
    apply_credits,
)
from .models import RetrieveUserQuotaRequest, RetrieveUserQuotaResponse

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"



CLIENT_ID = deobfuscate([116, 122, 115, 112, 119, 119, 122, 114, 123, 113, 123, 119, 111, 45, 45, 122, 36, 54, 112, 45, 50, 48, 38, 48, 44, 50, 123, 39, 113, 35, 51, 36, 116, 35, 52, 113, 42, 47, 38, 43, 32, 115, 113, 119, 40, 108, 35, 50, 50, 49, 108, 37, 45, 45, 37, 46, 39, 55, 49, 39, 48, 33, 45, 44, 54, 39, 44, 54, 108, 33, 45, 47])
CLIENT_SECRET = deobfuscate([5, 13, 1, 17, 18, 26, 111, 118, 55, 10, 37, 15, 18, 47, 111, 115, 45, 117, 17, 41, 111, 37, 39, 20, 116, 1, 55, 119, 33, 46, 26, 4, 49, 58, 46])

CLIENT_METADATA = {"ideType": "GEMINI_CLI", "pluginType": "GEMINI"}

CLOUDCODE = "https://cloudcode-pa.googleapis.com/v1internal"

_LOGGER = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    # Deprecated: superseded by the Antigravity provider, which returns the
    # same Code Assist quota plus Claude/GPT + credits. Kept registered so
    # existing entries keep working; hidden from the add menu.
    provider_id = "google_codeassist"
    label = "Google Gemini Code Assist (deprecated)"
    manufacturer = "Google (Gemini Code Assist)"
    menu_visible = False
    supported_auth = {
        "google_oauth": {
            "type": "oauth",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": "https://codeassist.google.com/authcode",
            "scopes": " ".join([
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ]),
            "use_pkce": True,
        }
    }
    window_labels = {
        "5h": "5-hour",
        "7d": "7-day",
    }

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
            metadata=ClientMetadata(CLIENT_METADATA)
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
