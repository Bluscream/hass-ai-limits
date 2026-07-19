"""Placeholder stubs for future providers."""

from __future__ import annotations

from ...models import LimitsData
from .base import AIProvider


class GeminiAPIProvider(AIProvider):
    provider_id = "gemini_api"
    label = "Gemini API Token (Google)"
    manufacturer = "Google"
    auth_type = "api_key"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")


class ChatGPTSubProvider(AIProvider):
    provider_id = "chatgpt_sub"
    label = "ChatGPT Subscription (OpenAI)"
    manufacturer = "OpenAI"
    auth_type = "cookie"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")


class ChatGPTAPIProvider(AIProvider):
    provider_id = "chatgpt_api"
    label = "ChatGPT API Token (OpenAI)"
    manufacturer = "OpenAI"
    auth_type = "api_key"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")


class CopilotSubProvider(AIProvider):
    provider_id = "copilot_sub"
    label = "Copilot Subscription (Microsoft)"
    manufacturer = "Microsoft"
    auth_type = "cookie"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")


class GithubCopilotProvider(AIProvider):
    provider_id = "github_copilot"
    label = "GitHub Copilot (GitHub)"
    manufacturer = "GitHub"
    auth_type = "cookie"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")


class PerplexitySubProvider(AIProvider):
    provider_id = "perplexity_sub"
    label = "Perplexity Subscription (Perplexity)"
    manufacturer = "Perplexity"
    auth_type = "cookie"

    async def async_fetch(self) -> LimitsData:
        return LimitsData(status="ok")
