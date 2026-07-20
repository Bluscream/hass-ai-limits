"""DeepSeek API provider."""

from __future__ import annotations

import logging
from aiohttp import ClientError

from ....models import LimitsData
from ..base import AIProvider, AuthError, CannotConnect

_LOGGER = logging.getLogger(__name__)

API_URL = "https://api.deepseek.com/user/balance"


class DeepSeekAPIProvider(AIProvider):
    """DeepSeek API balance and usage provider."""

    provider_id = "deepseek_api"
    label = "DeepSeek API Token (DeepSeek)"
    manufacturer = "DeepSeek"
    supported_auth = {"api_key": {"type": "api_key"}}

    async def async_fetch(self) -> LimitsData:
        api_key = self.entry.data.get("api_key", "").strip()
        if not api_key:
            return LimitsData(status="error", error="API key not found")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        try:
            resp = await self.session.get(API_URL, headers=headers)
        except ClientError as err:
            raise CannotConnect(f"Connection error: {err}") from err

        if resp.status == 401:
            raise AuthError("Invalid API key")
        if resp.status != 200:
            return LimitsData(status="error", error=f"HTTP {resp.status}")

        try:
            data = await resp.json()
        except ValueError:
            return LimitsData(status="error", error="Invalid JSON response")

        if not data.get("is_available", False):
            _LOGGER.warning("DeepSeek account balance is not available or exhausted")

        limits = LimitsData(status="ok")
        balance_infos = data.get("balance_infos", [])
        if balance_infos:
            info = balance_infos[0]
            try:
                limits.credits_available = float(info.get("total_balance", 0.0))
            except (ValueError, TypeError):
                pass

        return limits
