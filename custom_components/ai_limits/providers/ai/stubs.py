"""Stub providers for standard AI subscription/API services."""

from __future__ import annotations

import logging
from aiohttp import ClientError

from ...const import STATUS_ERROR
from ...models import LimitsData
from ..base import AIProvider

_LOGGER = logging.getLogger(__name__)


class GeminiAPIProvider(AIProvider):
    provider_id = "gemini_api"
    label = "Gemini API Token (Google)"
    manufacturer = "Google"
    supported_auth = {"api_key": {"type": "api_key"}}

    async def async_fetch(self) -> LimitsData:
        api_key = self.entry.data.get("api_key", "").strip()
        if not api_key:
            return LimitsData(status=STATUS_ERROR, error="API Key is missing")
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            resp = await self.session.get(url)
            if resp.status == 400:
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            elif resp.status >= 400:
                return LimitsData(status=STATUS_ERROR, error=f"HTTP {resp.status}")
            
            data = LimitsData(status="ok", plan="Gemini API Free Tier")
            data.update_window("1.5 Flash RPM", 0, 15, 60)
            data.update_window("1.5 Pro RPM", 0, 2, 60)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))


class ChatGPTSubProvider(AIProvider):
    provider_id = "chatgpt_sub"
    label = "ChatGPT Subscription (OpenAI)"
    manufacturer = "OpenAI"
    supported_auth = {"cookie": {"type": "cookie"}}

    async def async_fetch(self) -> LimitsData:
        cookie = self.entry.data.get("cookie", "").strip()
        if not cookie:
            return LimitsData(status=STATUS_ERROR, error="Cookie is missing")
        try:
            headers = {
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            resp = await self.session.get("https://chatgpt.com/backend-api/models", headers=headers)
            if resp.status in (401, 403):
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            elif resp.status >= 400:
                return LimitsData(status=STATUS_ERROR, error=f"HTTP {resp.status}")
            
            data = LimitsData(status="ok", plan="ChatGPT Plus")
            data.update_window("GPT-4o Cap", 0, 80, 3 * 3600)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))


class ChatGPTAPIProvider(AIProvider):
    provider_id = "chatgpt_api"
    label = "ChatGPT API Token (OpenAI)"
    manufacturer = "OpenAI"
    supported_auth = {"api_key": {"type": "api_key"}}

    async def async_fetch(self) -> LimitsData:
        api_key = self.entry.data.get("api_key", "").strip()
        if not api_key:
            return LimitsData(status=STATUS_ERROR, error="API Key is missing")
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = await self.session.get("https://api.openai.com/v1/models", headers=headers)
            if resp.status in (401, 403):
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            elif resp.status >= 400:
                return LimitsData(status=STATUS_ERROR, error=f"HTTP {resp.status}")
            
            data = LimitsData(status="ok", plan="OpenAI Developer API")
            try:
                import datetime
                today = datetime.date.today().isoformat()
                usage_resp = await self.session.get(
                    f"https://api.openai.com/v1/dashboard/billing/usage?start_date={today}&end_date={today}",
                    headers=headers
                )
                sub_resp = await self.session.get(
                    "https://api.openai.com/v1/dashboard/billing/subscription",
                    headers=headers
                )
                if usage_resp.status == 200 and sub_resp.status == 200:
                    usage_data = await usage_resp.json()
                    sub_data = await sub_resp.json()
                    limit = sub_data.get("hard_limit_usd", 120.0)
                    used = usage_data.get("total_usage", 0) / 100.0
                    data.update_window("Monthly Spend", used, limit, 30 * 86400)
                    return data
            except Exception:
                pass
            
            data.update_window("GPT-4o RPM", 0, 500, 60)
            data.update_window("GPT-4o TPM", 0, 30000, 60)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))


class CopilotSubProvider(AIProvider):
    provider_id = "copilot_sub"
    label = "Copilot Subscription (Microsoft)"
    manufacturer = "Microsoft"
    supported_auth = {"cookie": {"type": "cookie"}}

    async def async_fetch(self) -> LimitsData:
        cookie = self.entry.data.get("cookie", "").strip()
        if not cookie:
            return LimitsData(status=STATUS_ERROR, error="Cookie is missing")
        try:
            headers = {
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            resp = await self.session.get("https://www.bing.com/turing/conversation/chats", headers=headers)
            if resp.status in (401, 403):
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            
            data = LimitsData(status="ok", plan="Copilot Pro")
            data.update_window("Turns per Conversation", 0, 30, 3600)
            data.update_window("Daily Turn Limit", 0, 300, 86400)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))


class GithubCopilotProvider(AIProvider):
    provider_id = "github_copilot"
    label = "GitHub Copilot (GitHub)"
    manufacturer = "GitHub"
    supported_auth = {"cookie": {"type": "cookie"}}

    async def async_fetch(self) -> LimitsData:
        cookie = self.entry.data.get("cookie", "").strip()
        if not cookie:
            return LimitsData(status=STATUS_ERROR, error="Cookie/Token is missing")
        try:
            headers = {
                "Authorization": f"token {cookie}",
                "User-Agent": "HomeAssistant-AI-Limits",
            }
            resp = await self.session.get("https://api.github.com/copilot_user", headers=headers)
            if resp.status in (401, 403):
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            
            data = LimitsData(status="ok", plan="GitHub Copilot")
            data.update_window("Copilot Completions", 0, 500, 3600)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))


class PerplexitySubProvider(AIProvider):
    provider_id = "perplexity_sub"
    label = "Perplexity Subscription (Perplexity)"
    manufacturer = "Perplexity"
    supported_auth = {"cookie": {"type": "cookie"}}

    async def async_fetch(self) -> LimitsData:
        cookie = self.entry.data.get("cookie", "").strip()
        if not cookie:
            return LimitsData(status=STATUS_ERROR, error="Cookie is missing")
        try:
            headers = {
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            resp = await self.session.get("https://www.perplexity.ai/api/auth/session", headers=headers)
            if resp.status in (401, 403):
                return LimitsData(status=STATUS_ERROR, error="invalid_auth")
            
            data = LimitsData(status="ok", plan="Perplexity Pro")
            data.update_window("Daily Pro Queries", 0, 600, 86400)
            return data
        except Exception as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))
