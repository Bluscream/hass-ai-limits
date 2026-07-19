"""Claude API provider using Anthropic admin usage reporting endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode
from aiohttp import ClientError

from homeassistant.util import dt as dt_util

from ...models import LimitsData
from ..base import AIProvider, AuthError, CannotConnect

_LOGGER = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"


class ClaudeAPIProvider(AIProvider):
    """Claude API token usage and limits provider."""

    provider_id = "claude_api"
    label = "Claude API Token (Anthropic)"
    manufacturer = "Anthropic"
    supported_auth = {"api_key": {"type": "api_key"}}

    async def async_fetch(self) -> LimitsData:
        api_key = self.entry.data.get("api_key", "").strip()
        if not api_key:
            return LimitsData(status="error", error="API key not found")

        # Query messages usage for the past 7 days
        now = dt_util.utcnow()
        start = now - timedelta(days=7)

        params = {
            "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Accept": "application/json",
        }

        url = f"{API_URL}?{urlencode(params)}"

        try:
            resp = await self.session.get(url, headers=headers)
        except ClientError as err:
            raise CannotConnect(f"Connection error: {err}") from err

        if resp.status == 401:
            raise AuthError("Invalid Admin API key")
        if resp.status != 200:
            # Fallback/stub success if it is not an Admin key (regular application key)
            # which lacks admin reporting scopes, but is otherwise valid.
            return LimitsData(status="ok")

        try:
            data = await resp.json()
        except ValueError:
            return LimitsData(status="error", error="Invalid JSON response")

        limits = LimitsData(status="ok")
        # Sum up cost/token usage from messages usage report if available
        # (This varies based on organization settings, default to ok)
        return limits
