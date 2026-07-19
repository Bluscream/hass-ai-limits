"""Devin usage provider."""

from __future__ import annotations

import logging

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from ...const import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ...models import LimitsData, WindowData, to_datetime
from ..base import AIProvider, AuthError, CannotConnect

_LOGGER = logging.getLogger(__name__)

CONF_DEVIN_TOKEN = "devin_token"
CONF_DEVIN_ORG = "devin_org"


class DevinProvider(AIProvider):
    provider_id = "devin"
    label = "Devin"
    manufacturer = "Cognition AI"
    supported_auth = {
        "devin": {
            "type": "devin",
        },
        "github_oauth": {
            "type": "oauth",
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://app.devin.ai/api/auth1/github/exchange",
            "client_id": "Iv1.fffb955bc006997f",
            "scopes": "user:email",
            "redirect_uri": "https://app.devin.ai/auth/callback",
        },
        "google_oauth": {
            "type": "oauth",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://app.devin.ai/api/auth1/google/exchange",
            "client_id": "686954959906-ta39pvm0f0hmc71nbou45j6c0liulmfe.apps.googleusercontent.com",
            "scopes": "openid email profile",
            "redirect_uri": "https://app.devin.ai/auth/callback",
            "use_pkce": True,
        }
    }
    window_labels = {
        "daily": "Daily quota",
        "weekly": "Weekly quota",
    }

    @property
    def _name(self) -> str:
        return self.entry.title

    async def async_fetch(self) -> LimitsData:
        token = self.entry.data.get(CONF_DEVIN_TOKEN, "").strip()
        org_id = self.entry.data.get(CONF_DEVIN_ORG, "").strip()

        if not token or not org_id:
            return LimitsData(status=STATUS_ERROR, error="Missing Devin credentials")

        headers = {
            "Authorization": f"Bearer {token}",
            "x-cog-org-id": org_id,
            "Accept": "application/json",
        }

        data = LimitsData(status=STATUS_OK)

        # 1. Fetch quota usage
        quota_url = f"https://app.devin.ai/api/{org_id}/billing/quota/usage"
        try:
            resp = await self.session.get(quota_url, headers=headers)
        except ClientError as err:
            _LOGGER.error("Devin quota request failed for %s: %s", self._name, err)
            raise CannotConnect(f"Connection failed: {err}")

        if resp.status in (401, 403):
            raise AuthError("Invalid auth token or organization ID")
        elif resp.status >= 400:
            data.status = STATUS_ERROR
            data.error = f"HTTP error {resp.status} on quota"
            return data

        try:
            quota_data = await resp.json()
        except (ClientError, ValueError) as err:
            data.status = STATUS_ERROR
            data.error = f"Invalid quota JSON: {err}"
            return data

        # 2. Fetch billing status
        status_url = f"https://app.devin.ai/api/{org_id}/billing/status"
        try:
            resp_status = await self.session.get(status_url, headers=headers)
        except ClientError as err:
            _LOGGER.error("Devin status request failed for %s: %s", self._name, err)
            raise CannotConnect(f"Connection failed: {err}")

        billing_status = {}
        if resp_status.status == 200:
            try:
                billing_status = await resp_status.json()
            except (ClientError, ValueError):
                pass

        # Populate plan & credits details
        data.plan = billing_status.get("plan_slug", "free")
        data.credits_available = billing_status.get("overage_credits")

        # Parse windows
        daily_pct = quota_data.get("daily_percentage", 0)
        weekly_pct = quota_data.get("weekly_percentage", 0)

        # Normalize percentages (0..100) to utilization (0..1)
        daily_util = float(daily_pct) / 100.0 if daily_pct is not None else 0.0
        weekly_util = float(weekly_pct) / 100.0 if weekly_pct is not None else 0.0

        daily_reset = to_datetime(quota_data.get("daily_reset_at"))
        weekly_reset = to_datetime(quota_data.get("weekly_reset_at"))

        data.windows["daily"] = WindowData(
            status="ok",
            utilization=daily_util,
            resets_at=daily_reset,
            label="Daily quota",
            group="Quota",
        )

        data.windows["weekly"] = WindowData(
            status="ok",
            utilization=weekly_util,
            resets_at=weekly_reset,
            label="Weekly quota",
            group="Quota",
        )

        # Update status if rate limited (percentage >= 100)
        if daily_pct >= 100 or weekly_pct >= 100:
            data.status = STATUS_RATE_LIMITED
            if daily_pct >= 100:
                data.windows["daily"].status = "rate_limited"
            if weekly_pct >= 100:
                data.windows["weekly"].status = "rate_limited"

        data.recompute_reset_in(dt_util.utcnow())
        data.raw = {
            "quota": quota_data,
            "status": billing_status,
        }

        return data


async def async_validate(
    hass: HomeAssistant, token: str, org_id: str
) -> None:
    """Config-time probe. Raises AuthError / CannotConnect on failure."""
    session = async_get_clientsession(hass)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-cog-org-id": org_id,
        "Accept": "application/json",
    }
    quota_url = f"https://app.devin.ai/api/{org_id}/billing/quota/usage"
    try:
        resp = await session.get(quota_url, headers=headers)
    except ClientError as err:
        raise CannotConnect(str(err)) from err

    if resp.status in (401, 403):
        raise AuthError("Invalid auth token or organization ID")
    if resp.status != 200:
        raise CannotConnect(f"HTTP {resp.status}")
