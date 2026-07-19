"""Config and options flow for AI Limits."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_NAME,
    CONF_COOKIE,
    CONF_DELETE_AFTER,
    CONF_ENABLE_PROBE,
    CONF_EXPIRES_AT,
    CONF_ORG_UUID,
    CONF_PROBE_MODEL,
    CONF_PROVIDER,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_AGENT,
    DEFAULT_DELETE_AFTER,
    DEFAULT_ENABLE_PROBE,
    DEFAULT_PROBE_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USER_AGENT,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PROVIDER_ANTIGRAVITY,
    PROVIDER_CLAUDE_WEB,
    PROVIDER_GOOGLE_CA,
)
from .providers import menu_options, oauth
from .providers.antigravity import CLIENT as AG_CLIENT
from .providers.base import AuthError, CannotConnect
from .providers.claude import async_validate as validate_claude
from .providers.gemini import CLIENT as GM_CLIENT

_COOKIE_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=True)
)


class AILimitsConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per account."""

    VERSION = 1

    def __init__(self) -> None:
        self._verifier: str | None = None
        self._state: str | None = None
        self._auth_url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=menu_options())

    # --- Claude web session -------------------------------------------

    async def async_step_claude_web(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            cookie = user_input[CONF_COOKIE].strip()
            user_agent = user_input.get(CONF_USER_AGENT, "").strip() or None

            await self.async_set_unique_id(f"claude_web:{name.lower()}")
            self._abort_if_unique_id_configured()

            org_uuid = None
            try:
                org = await validate_claude(self.hass, cookie, user_agent)
                org_uuid = org.uuid
            except AuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Claude subscription - {name}",
                    data={
                        CONF_PROVIDER: PROVIDER_CLAUDE_WEB,
                        CONF_ACCOUNT_NAME: name,
                        CONF_COOKIE: cookie,
                        CONF_USER_AGENT: user_agent or DEFAULT_USER_AGENT,
                        CONF_ORG_UUID: org_uuid,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): str,
                vol.Required(CONF_COOKIE): _COOKIE_SELECTOR,
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): str,
            }
        )
        return self.async_show_form(
            step_id="claude_web", data_schema=schema, errors=errors
        )

    # --- OAuth providers (paste flow) ---------------------------------

    async def _async_oauth_step(
        self,
        step_id: str,
        provider_id: str,
        client,
        title_prefix: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if self._state is None:
            self._state = oauth.new_state()
            challenge = None
            if client.use_pkce:
                self._verifier, challenge = oauth.generate_pkce()
            self._auth_url = oauth.build_authorize_url(client, self._state, challenge)

        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            code = oauth.extract_code(user_input["authorization_code"])
            await self.async_set_unique_id(f"{provider_id}:{name.lower()}")
            self._abort_if_unique_id_configured()
            if not code:
                errors["base"] = "oauth_failed"
            else:
                try:
                    tokens = await oauth.async_exchange_code(
                        self.hass, client, code, self._verifier
                    )
                except oauth.OAuthError:
                    errors["base"] = "oauth_failed"
                else:
                    return self.async_create_entry(
                        title=f"{title_prefix} - {name}",
                        data={
                            CONF_PROVIDER: provider_id,
                            CONF_ACCOUNT_NAME: name,
                            CONF_ACCESS_TOKEN: tokens.access_token,
                            CONF_REFRESH_TOKEN: tokens.refresh_token,
                            CONF_EXPIRES_AT: tokens.expires_at,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): str,
                vol.Required("authorization_code"): str,
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"auth_url": self._auth_url},
        )

    async def async_step_antigravity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_oauth_step(
            "antigravity", PROVIDER_ANTIGRAVITY, AG_CLIENT, "Antigravity", user_input
        )

    async def async_step_google_codeassist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_oauth_step(
            "google_codeassist",
            PROVIDER_GOOGLE_CA,
            GM_CLIENT,
            "Gemini Code Assist",
            user_input,
        )

    # --- Reauth -------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        provider = entry.data[CONF_PROVIDER]
        if provider == PROVIDER_GOOGLE_CA:
            return await self.async_step_google_codeassist()
        if provider == PROVIDER_ANTIGRAVITY:
            return await self.async_step_antigravity()

        errors: dict[str, str] = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            try:
                await validate_claude(
                    self.hass, cookie, entry.data.get(CONF_USER_AGENT)
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_COOKIE: cookie}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE): _COOKIE_SELECTOR}),
            errors=errors,
            description_placeholders={"account": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> AILimitsOptionsFlow:
        return AILimitsOptionsFlow()


class AILimitsOptionsFlow(OptionsFlow):
    """The 'Configure' button. Edits account details AND runtime options."""

    _DATA_KEYS = (CONF_ACCOUNT_NAME, CONF_COOKIE, CONF_USER_AGENT)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        provider = entry.data[CONF_PROVIDER]

        if user_input is not None:
            new_data = dict(entry.data)
            name = user_input.get(CONF_ACCOUNT_NAME, "").strip()
            if name:
                new_data[CONF_ACCOUNT_NAME] = name
            if user_input.get(CONF_COOKIE, "").strip():
                new_data[CONF_COOKIE] = user_input[CONF_COOKIE].strip()
            if user_input.get(CONF_USER_AGENT, "").strip():
                new_data[CONF_USER_AGENT] = user_input[CONF_USER_AGENT].strip()

            _name = new_data.get(CONF_ACCOUNT_NAME, "")
            titles = {
                PROVIDER_CLAUDE_WEB: f"Claude subscription - {_name}",
                PROVIDER_ANTIGRAVITY: f"Antigravity - {_name}",
                PROVIDER_GOOGLE_CA: f"Gemini Code Assist - {_name}",
            }
            self.hass.config_entries.async_update_entry(
                entry, data=new_data, title=titles.get(provider, entry.title)
            )
            options = {
                k: v for k, v in user_input.items() if k not in self._DATA_KEYS
            }
            return self.async_create_entry(data=options)

        data = entry.data
        opts = entry.options
        scan_field = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=86400,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            )
        }
        fields: dict[Any, Any] = {
            vol.Required(
                CONF_ACCOUNT_NAME, default=data.get(CONF_ACCOUNT_NAME, "")
            ): str,
        }
        if provider == PROVIDER_CLAUDE_WEB:
            fields[vol.Optional(CONF_COOKIE)] = _COOKIE_SELECTOR
            fields[
                vol.Optional(
                    CONF_USER_AGENT, default=data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT)
                )
            ] = str
            fields[
                vol.Required(
                    CONF_ENABLE_PROBE,
                    default=opts.get(CONF_ENABLE_PROBE, DEFAULT_ENABLE_PROBE),
                )
            ] = BooleanSelector()
            fields[
                vol.Required(
                    CONF_DELETE_AFTER,
                    default=opts.get(CONF_DELETE_AFTER, DEFAULT_DELETE_AFTER),
                )
            ] = BooleanSelector()
            fields[
                vol.Optional(
                    CONF_PROBE_MODEL,
                    default=opts.get(CONF_PROBE_MODEL, DEFAULT_PROBE_MODEL),
                )
            ] = str
        fields.update(scan_field)
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
