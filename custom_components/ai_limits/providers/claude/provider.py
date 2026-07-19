"""Claude subscription usage via a claude.ai web session (cookie).

Reads the passive /usage endpoint the Claude desktop app polls. An optional
active probe (sends a throwaway completion) is a fallback for accounts where
/usage returns nothing. Unofficial: private endpoints, user's own cookie.
"""

from __future__ import annotations

import json
import logging
import uuid

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from ...const import (
    CONF_COOKIE,
    CONF_DELETE_AFTER,
    CONF_ENABLE_PROBE,
    CONF_ORG_UUID,
    CONF_PROBE_MODEL,
    CONF_USER_AGENT,
    DEFAULT_DELETE_AFTER,
    DEFAULT_ENABLE_PROBE,
    DEFAULT_PROBE_MODEL,
    DEFAULT_USER_AGENT,
    PROVIDER_CLAUDE_WEB,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
)
from ...models import LimitsData
from ..base import AIProvider, AuthError, CannotConnect
from .models import ClaudeOrganization, CompletionRequest, MessageLimit, UsageReport

_LOGGER = logging.getLogger(__name__)
BASE_URL = "https://claude.ai"


def _find_dict(obj, key: str):
    if isinstance(obj, dict):
        if isinstance(obj.get(key), dict):
            return obj[key]
        for value in obj.values():
            found = _find_dict(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_dict(item, key)
            if found is not None:
                return found
    return None


def _trim_raw(obj, depth: int = 0):
    if depth > 4:
        return "..."
    if isinstance(obj, dict):
        return {k: _trim_raw(v, depth + 1) for k, v in list(obj.items())[:30]}
    if isinstance(obj, list):
        return [_trim_raw(v, depth + 1) for v in obj[:15]]
    if isinstance(obj, str) and len(obj) > 200:
        return obj[:200] + "..."
    return obj


class ClaudeWebProvider(AIProvider):
    provider_id = PROVIDER_CLAUDE_WEB
    label = "Claude subscription (web session)"
    manufacturer = "Anthropic (claude.ai)"

    def __init__(self, hass, entry) -> None:
        super().__init__(hass, entry)
        d = entry.data
        self._cookie = d[CONF_COOKIE]
        self._user_agent = d.get(CONF_USER_AGENT) or DEFAULT_USER_AGENT
        self._org_uuid = d.get(CONF_ORG_UUID)
        self._device_id = str(uuid.uuid4())

    # -- config-time helper (no entry) ---------------------------------

    @classmethod
    def for_credentials(
        cls, hass: HomeAssistant, cookie: str, user_agent: str | None
    ) -> ClaudeWebProvider:
        obj = cls.__new__(cls)
        obj.hass = hass
        obj.entry = None
        obj.session = async_get_clientsession(hass)
        obj._cookie = cookie
        obj._user_agent = user_agent or DEFAULT_USER_AGENT
        obj._org_uuid = None
        obj._device_id = str(uuid.uuid4())
        return obj

    def _headers(self, sse: bool = False) -> dict[str, str]:
        return {
            "Cookie": self._cookie,
            "User-Agent": self._user_agent,
            "Accept": "text/event-stream" if sse else "application/json",
            "Content-Type": "application/json",
            "Referer": f"{BASE_URL}/",
            "Origin": BASE_URL,
            "anthropic-client-platform": "web_claude_ai",
            "anthropic-device-id": self._device_id,
        }

    async def async_discover_org(self) -> ClaudeOrganization:
        try:
            resp = await self.session.get(
                f"{BASE_URL}/api/organizations", headers=self._headers()
            )
        except ClientError as err:
            raise CannotConnect(str(err)) from err
        if resp.status in (401, 403):
            raise AuthError(f"HTTP {resp.status}")
        if resp.status != 200:
            raise CannotConnect(f"HTTP {resp.status}")
        try:
            orgs = await resp.json(content_type=None)
        except (ClientError, ValueError) as err:
            raise CannotConnect(f"bad_json: {err}") from err
        if not isinstance(orgs, list) or not orgs:
            raise CannotConnect("no organizations")
        parsed = [ClaudeOrganization.from_dict(o) for o in orgs]
        for org in parsed:
            if org.is_chat_org:
                return org
        return parsed[0]

    def _options(self) -> dict:
        return self.entry.options if self.entry is not None else {}

    async def _ensure_org(self) -> str:
        if self._org_uuid:
            return self._org_uuid
        org = await self.async_discover_org()
        self._org_uuid = org.uuid
        if self.entry is not None:
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, CONF_ORG_UUID: self._org_uuid}
            )
        return self._org_uuid

    async def async_fetch(self) -> LimitsData:
        opts = self._options()
        try:
            org_uuid = await self._ensure_org()
        except AuthError as err:
            return LimitsData(status=STATUS_ERROR, error=f"invalid_auth: {err}")
        except CannotConnect as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))

        data = await self._fetch_org_meta(org_uuid)
        if data.status == STATUS_ERROR:
            _LOGGER.warning(
                "Claude %s: org lookup failed (%s)", self.entry.title, data.error
            )
            return data

        await self._fetch_usage(org_uuid, data)
        if not data.windows and opts.get(CONF_ENABLE_PROBE, DEFAULT_ENABLE_PROBE):
            _LOGGER.debug("Claude %s: /usage empty, running probe", self.entry.title)
            await self._probe(org_uuid, data, opts)

        data.recompute_reset_in(dt_util.utcnow())
        _LOGGER.debug(
            "Claude %s: status=%s plan=%s windows=%s",
            self.entry.title,
            data.status,
            data.plan,
            list(data.windows),
        )
        return data

    async def _fetch_org_meta(self, org_uuid: str) -> LimitsData:
        try:
            resp = await self.session.get(
                f"{BASE_URL}/api/organizations/{org_uuid}", headers=self._headers()
            )
        except ClientError as err:
            return LimitsData(status=STATUS_ERROR, error=str(err))
        if resp.status in (401, 403):
            return LimitsData(status=STATUS_ERROR, error="invalid_auth")
        if resp.status >= 400:
            return LimitsData(status=STATUS_ERROR, error=f"HTTP {resp.status}")
        try:
            org = ClaudeOrganization.from_dict(await resp.json(content_type=None))
        except (ClientError, ValueError) as err:
            return LimitsData(status=STATUS_ERROR, error=f"bad_json: {err}")
        return LimitsData(
            status=STATUS_OK,
            plan=org.plan,
            tier=org.rate_limit_tier,
            raw={"capabilities": org.capabilities, "billing_type": org.billing_type},
        )

    async def _fetch_usage(self, org_uuid: str, data: LimitsData) -> None:
        try:
            resp = await self.session.get(
                f"{BASE_URL}/api/organizations/{org_uuid}/usage",
                headers=self._headers(),
            )
        except ClientError as err:
            data.error = f"usage: {err}"
            return
        if resp.status == 429:
            data.status = STATUS_RATE_LIMITED
            return
        if resp.status in (401, 403):
            _LOGGER.warning(
                "Claude %s: /usage auth error (%s); cookie likely expired",
                self.entry.title,
                resp.status,
            )
            data.status = STATUS_ERROR
            data.error = "invalid_auth"
            return
        if resp.status >= 400:
            _LOGGER.warning(
                "Claude %s: /usage HTTP %s", self.entry.title, resp.status
            )
            data.error = f"usage HTTP {resp.status}"
            return
        try:
            payload = await resp.json(content_type=None)
        except (ClientError, ValueError) as err:
            data.error = f"usage bad_json: {err}"
            return

        report = UsageReport.from_dict(payload)
        if report.windows:
            data.windows.update(report.windows)
            if report.is_limited:
                data.status = STATUS_RATE_LIMITED
            data.raw = {**data.raw, "severity": report.severity}
        else:
            data.raw = {**data.raw, "usage_payload": _trim_raw(payload)}

    async def _probe(self, org_uuid: str, data: LimitsData, opts: dict) -> None:
        model = opts.get(CONF_PROBE_MODEL) or DEFAULT_PROBE_MODEL
        conv_uuid = str(uuid.uuid4())
        request = CompletionRequest(
            prompt=".",
            model=model,
            turn_message_uuids={
                "human_message_uuid": str(uuid.uuid4()),
                "assistant_message_uuid": str(uuid.uuid4()),
            },
        )
        url = (
            f"{BASE_URL}/api/organizations/{org_uuid}"
            f"/chat_conversations/{conv_uuid}/completion"
        )
        try:
            resp = await self.session.post(
                url, headers=self._headers(sse=True), json=request.to_dict()
            )
        except ClientError as err:
            data.error = f"probe: {err}"
            return
        if resp.status == 429:
            data.status = STATUS_RATE_LIMITED
            return
        if resp.status >= 400:
            data.error = f"probe HTTP {resp.status}"
            return
        try:
            text = await resp.text()
        except ClientError as err:
            data.error = f"probe read: {err}"
            return

        ml = _extract_message_limit(text)
        if ml is not None:
            data.windows.update(ml.windows)
            if ml.is_limited:
                data.status = STATUS_RATE_LIMITED

        if opts.get(CONF_DELETE_AFTER, DEFAULT_DELETE_AFTER):
            await self._delete_conversation(org_uuid, conv_uuid)

    async def _delete_conversation(self, org_uuid: str, conv_uuid: str) -> None:
        url = (
            f"{BASE_URL}/api/organizations/{org_uuid}"
            f"/chat_conversations/{conv_uuid}"
        )
        try:
            await self.session.delete(url, headers=self._headers())
        except ClientError as err:
            _LOGGER.debug("Could not delete probe conversation: %s", err)


def _extract_message_limit(sse_text: str) -> MessageLimit | None:
    for line in sse_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            obj = json.loads(chunk)
        except ValueError:
            continue
        if obj.get("type") == "message_limit":
            return MessageLimit.from_dict(obj.get("message_limit") or {})
    return None


async def async_validate(
    hass: HomeAssistant, cookie: str, user_agent: str | None
) -> ClaudeOrganization:
    """Config-time probe. Raises AuthError / CannotConnect on failure."""
    provider = ClaudeWebProvider.for_credentials(hass, cookie, user_agent)
    return await provider.async_discover_org()
