"""OpenRouter API provider."""

from __future__ import annotations

import logging
from aiohttp import ClientError

from ...models import LimitsData
from ..base import AIProvider, AuthError, CannotConnect

_LOGGER = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/key"


class OpenRouterAPIProvider(AIProvider):
    """OpenRouter API key usage and limits provider."""

    provider_id = "openrouter_api"
    label = "OpenRouter API Token (OpenRouter)"
    manufacturer = "OpenRouter"
    supported_auth = {"api_key": {"type": "api_key"}}

    async def async_fetch(self) -> LimitsData:
        api_key = self.entry.data.get("api_key", "").strip()
        if not api_key:
            return LimitsData(status="error", error="API key not found")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
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

        # OpenRouter returns data wrapped in a "data" object
        key_data = data.get("data", {})
        limits = LimitsData(status="ok")

        # remaining spend limit (in USD)
        limit_remaining = key_data.get("limit_remaining")
        if limit_remaining is not None:
            try:
                # If key has no limit set, it may be null/None or a large number
                limits.credits_available = float(limit_remaining)
            except (ValueError, TypeError):
                pass
        else:
            # If there is no specific key limit, try using overall account credits
            try:
                credits_resp = await self.session.get("https://openrouter.ai/api/v1/credits", headers=headers)
                if credits_resp.status == 200:
                    credits_data = await credits_resp.json()
                    total_credits = credits_data.get("data", {}).get("total_credits", 0.0)
                    limits.credits_available = float(total_credits)
            except Exception as err:
                _LOGGER.debug("Could not fetch overall OpenRouter credits: %s", err)

        return limits
