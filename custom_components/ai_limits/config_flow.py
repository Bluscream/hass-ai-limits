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
    CONF_ACCOUNT_NAME,
    CONF_DELETE_AFTER,
    CONF_ENABLE_PROBE,
    CONF_PROBE_MODEL,
    CONF_PROVIDER,
    CONF_SCAN_INTERVAL,
    DEFAULT_DELETE_AFTER,
    DEFAULT_ENABLE_PROBE,
    DEFAULT_PROBE_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .providers import REGISTRY, menu_options, AuthError, CannotConnect
from .providers.auth import OAuthProvider, OAuthError
from .providers.ai.claude import async_validate as validate_claude
from .providers.ai.claude.provider import DEFAULT_USER_AGENT
from .providers.ai.devin import async_validate as validate_devin

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
        self._target_provider: str | None = None
        self._selected_entry_id: str | None = None
        self._reused_data: dict[str, Any] | None = None

    def _get_credential_types(self, provider: str | None) -> list[str]:
        if not provider:
            return []
        cls = REGISTRY.get(provider)
        if cls:
            return list(cls.supported_auth.keys())
        return []

    def _get_matching_entries(self, credential_types: list[str]) -> list[ConfigEntry]:
        if not credential_types:
            return []
        entries = self.hass.config_entries.async_entries(DOMAIN)
        matching = []
        for entry in entries:
            entry_prov = entry.data.get(CONF_PROVIDER)
            entry_types = self._get_credential_types(entry_prov)
            if any(t in credential_types for t in entry_types):
                matching.append(entry)
        return matching

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Reset provider context on menu start
        self._target_provider = None
        self._selected_entry_id = None
        self._reused_data = None
        return self.async_show_menu(step_id="user", menu_options=menu_options())

    async def async_step_select_saved_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        cred_types = self._get_credential_types(self._target_provider)
        matching = self._get_matching_entries(cred_types)

        if user_input is not None:
            selection = user_input["saved_login"]
            if selection == "new_login":
                self._selected_entry_id = "new"
                return await getattr(self, f"async_step_{self._target_provider}")()
            else:
                entry = next(e for e in matching if e.entry_id == selection)
                # Copy credentials
                self._reused_data = dict(entry.data)
                self._reused_data[CONF_PROVIDER] = self._target_provider
                return await self.async_step_reused_name()

        options = {}
        for entry in matching:
            entry_prov = entry.data.get(CONF_PROVIDER)
            cls = REGISTRY.get(entry_prov)
            lbl = cls.label if cls else entry_prov
            options[entry.entry_id] = f"{entry.data.get(CONF_ACCOUNT_NAME)} ({lbl})"
        options["new_login"] = "Log in with new credentials"

        schema = vol.Schema({
            vol.Required("saved_login", default="new_login"): vol.In(options)
        })

        return self.async_show_form(
            step_id="select_saved_login",
            data_schema=schema,
            errors=errors
        )

    async def async_step_reused_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            self._reused_data[CONF_ACCOUNT_NAME] = name

            await self.async_set_unique_id(f"{self._target_provider}:{name.lower()}")
            self._abort_if_unique_id_configured()

            cls = REGISTRY.get(self._target_provider)
            lbl = cls.label if cls else self._target_provider
            return self.async_create_entry(
                title=f"{lbl} - {name}",
                data=self._reused_data,
            )

        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str
        })
        return self.async_show_form(
            step_id="reused_name",
            data_schema=schema,
            errors=errors
        )

    # --- Claude web session -------------------------------------------

    async def async_step_claude_web(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "claude_web"
            cred_types = self._get_credential_types("claude_web")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            cookie = user_input["cookie"].strip()
            user_agent = user_input.get("user_agent", "").strip() or None

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
                        CONF_PROVIDER: "claude_web",
                        CONF_ACCOUNT_NAME: name,
                        "cookie": cookie,
                        "user_agent": user_agent or DEFAULT_USER_AGENT,
                        "org_uuid": org_uuid,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): str,
                vol.Required("cookie"): _COOKIE_SELECTOR,
                vol.Optional("user_agent", default=DEFAULT_USER_AGENT): str,
            }
        )
        return self.async_show_form(
            step_id="claude_web", data_schema=schema, errors=errors
        )

    # --- Devin --------------------------------------------------------

    async def async_step_devin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "devin"
            cred_types = self._get_credential_types("devin")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        return self.async_show_menu(
            step_id="devin",
            menu_options={
                "devin_google_oauth": "Log in via Google",
                "devin_github_oauth": "Log in via GitHub",
                "devin_token": "Log in via Direct Bearer Token",
            }
        )

    async def async_step_devin_google_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_oauth_step(
            "devin_google_oauth", "devin", "google_oauth", "Devin Google", user_input
        )

    async def async_step_devin_github_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_oauth_step(
            "devin_github_oauth", "devin", "github_oauth", "Devin GitHub", user_input
        )

    async def async_step_devin_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            token = user_input["devin_token"].strip()
            org_id = user_input["devin_org"].strip()

            await self.async_set_unique_id(f"devin:{org_id.lower()}:{name.lower()}")
            self._abort_if_unique_id_configured()

            try:
                await validate_devin(self.hass, token, org_id)
            except AuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Devin - {name}",
                    data={
                        CONF_PROVIDER: "devin",
                        CONF_ACCOUNT_NAME: name,
                        "devin_token": token,
                        "devin_org": org_id,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): str,
                vol.Required("devin_token"): str,
                vol.Required("devin_org"): str,
            }
        )
        return self.async_show_form(
            step_id="devin_token", data_schema=schema, errors=errors
        )

    # --- OAuth providers (paste flow) ---------------------------------

    async def _async_oauth_step(
        self,
        step_id: str,
        provider_id: str,
        auth_type_id: str,
        title_prefix: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = provider_id
            cred_types = self._get_credential_types(provider_id)
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        client_config = REGISTRY[provider_id].supported_auth[auth_type_id]

        errors: dict[str, str] = {}
        auth_provider = OAuthProvider(self.hass, client_config)
        if self._state is None:
            self._state = auth_provider.new_state()
            challenge = None
            if client_config.get("use_pkce"):
                self._verifier, challenge = auth_provider.generate_pkce()
            self._auth_url = auth_provider.build_authorize_url(self._state, challenge)

        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            code = auth_provider.extract_code(user_input["authorization_code"])
            await self.async_set_unique_id(f"{provider_id}:{name.lower()}")
            self._abort_if_unique_id_configured()
            if not code:
                errors["base"] = "oauth_failed"
            else:
                try:
                    tokens = await auth_provider.async_exchange_code(
                        code, self._verifier
                    )
                except OAuthError:
                    errors["base"] = "oauth_failed"
                else:
                    return self.async_create_entry(
                        title=f"{title_prefix} - {name}",
                        data={
                            CONF_PROVIDER: provider_id,
                            CONF_ACCOUNT_NAME: name,
                            "access_token": tokens.access_token,
                            "refresh_token": tokens.refresh_token,
                            "expires_at": tokens.expires_at,
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
            "antigravity", "antigravity", "google_oauth", "Antigravity", user_input
        )

    async def async_step_google_codeassist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_oauth_step(
            "google_codeassist",
            "google_codeassist",
            "google_oauth",
            "Gemini Code Assist",
            user_input,
        )

    async def async_step_claude_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "claude_api"
            cred_types = self._get_credential_types("claude_api")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            api_key = user_input["api_key"].strip()
            await self.async_set_unique_id(f"claude_api:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Claude API - {name}",
                data={
                    CONF_PROVIDER: "claude_api",
                    CONF_ACCOUNT_NAME: name,
                    "api_key": api_key,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
            vol.Required("api_key"): str,
        })
        return self.async_show_form(step_id="claude_api", data_schema=schema, errors=errors)


    async def async_step_gemini_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "gemini_api"
            cred_types = self._get_credential_types("gemini_api")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            api_key = user_input["api_key"].strip()
            await self.async_set_unique_id(f"gemini_api:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Gemini API - {name}",
                data={
                    CONF_PROVIDER: "gemini_api",
                    CONF_ACCOUNT_NAME: name,
                    "api_key": api_key,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
            vol.Required("api_key"): str,
        })
        return self.async_show_form(step_id="gemini_api", data_schema=schema, errors=errors)

    async def async_step_chatgpt_sub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "chatgpt_sub"
            cred_types = self._get_credential_types("chatgpt_sub")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            await self.async_set_unique_id(f"chatgpt_sub:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"ChatGPT Subscription - {name}",
                data={
                    CONF_PROVIDER: "chatgpt_sub",
                    CONF_ACCOUNT_NAME: name,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
        })
        return self.async_show_form(step_id="chatgpt_sub", data_schema=schema, errors=errors)

    async def async_step_chatgpt_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "chatgpt_api"
            cred_types = self._get_credential_types("chatgpt_api")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            api_key = user_input["api_key"].strip()
            await self.async_set_unique_id(f"chatgpt_api:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"ChatGPT API - {name}",
                data={
                    CONF_PROVIDER: "chatgpt_api",
                    CONF_ACCOUNT_NAME: name,
                    "api_key": api_key,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
            vol.Required("api_key"): str,
        })
        return self.async_show_form(step_id="chatgpt_api", data_schema=schema, errors=errors)

    async def async_step_copilot_sub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "copilot_sub"
            cred_types = self._get_credential_types("copilot_sub")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            await self.async_set_unique_id(f"copilot_sub:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Copilot - {name}",
                data={
                    CONF_PROVIDER: "copilot_sub",
                    CONF_ACCOUNT_NAME: name,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
        })
        return self.async_show_form(step_id="copilot_sub", data_schema=schema, errors=errors)

    async def async_step_github_copilot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "github_copilot"
            cred_types = self._get_credential_types("github_copilot")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            await self.async_set_unique_id(f"github_copilot:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"GitHub Copilot - {name}",
                data={
                    CONF_PROVIDER: "github_copilot",
                    CONF_ACCOUNT_NAME: name,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
        })
        return self.async_show_form(step_id="github_copilot", data_schema=schema, errors=errors)

    async def async_step_deepseek_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "deepseek_api"
            cred_types = self._get_credential_types("deepseek_api")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            api_key = user_input["api_key"].strip()
            await self.async_set_unique_id(f"deepseek_api:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"DeepSeek API - {name}",
                data={
                    CONF_PROVIDER: "deepseek_api",
                    CONF_ACCOUNT_NAME: name,
                    "api_key": api_key,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
            vol.Required("api_key"): str,
        })
        return self.async_show_form(step_id="deepseek_api", data_schema=schema, errors=errors)

    async def async_step_openrouter_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "openrouter_api"
            cred_types = self._get_credential_types("openrouter_api")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            api_key = user_input["api_key"].strip()
            await self.async_set_unique_id(f"openrouter_api:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"OpenRouter API - {name}",
                data={
                    CONF_PROVIDER: "openrouter_api",
                    CONF_ACCOUNT_NAME: name,
                    "api_key": api_key,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
            vol.Required("api_key"): str,
        })
        return self.async_show_form(step_id="openrouter_api", data_schema=schema, errors=errors)

    async def async_step_perplexity_sub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._selected_entry_id is None and self._target_provider is None:
            self._target_provider = "perplexity_sub"
            cred_types = self._get_credential_types("perplexity_sub")
            matching = self._get_matching_entries(cred_types)
            if matching:
                return await self.async_step_select_saved_login()

        errors = {}
        if user_input is not None:
            name = user_input[CONF_ACCOUNT_NAME].strip()
            await self.async_set_unique_id(f"perplexity_sub:{name.lower()}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Perplexity - {name}",
                data={
                    CONF_PROVIDER: "perplexity_sub",
                    CONF_ACCOUNT_NAME: name,
                },
            )
        schema = vol.Schema({
            vol.Required(CONF_ACCOUNT_NAME): str,
        })
        return self.async_show_form(step_id="perplexity_sub", data_schema=schema, errors=errors)

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
        if provider == "google_codeassist":
            return await self.async_step_google_codeassist()
        if provider == "antigravity":
            return await self.async_step_antigravity()

        errors: dict[str, str] = {}
        if user_input is not None:
            cookie = user_input["cookie"].strip()
            try:
                await validate_claude(
                    self.hass, cookie, entry.data.get("user_agent")
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, "cookie": cookie}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("cookie"): _COOKIE_SELECTOR}),
            errors=errors,
            description_placeholders={"account": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> AILimitsOptionsFlow:
        return AILimitsOptionsFlow()


class AILimitsOptionsFlow(OptionsFlow):
    """The 'Configure' button. Edits account details AND runtime options."""

    _DATA_KEYS = (CONF_ACCOUNT_NAME, "cookie", "user_agent")

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
            if user_input.get("cookie", "").strip():
                new_data["cookie"] = user_input["cookie"].strip()
            if user_input.get("user_agent", "").strip():
                new_data["user_agent"] = user_input["user_agent"].strip()

            _name = new_data.get(CONF_ACCOUNT_NAME, "")
            titles = {
                "claude_web": f"Claude subscription - {_name}",
                "antigravity": f"Antigravity - {_name}",
                "google_codeassist": f"Gemini Code Assist - {_name}",
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
        if provider == "claude_web":
            fields[vol.Optional("cookie")] = _COOKIE_SELECTOR
            fields[
                vol.Optional(
                    "user_agent", default=data.get("user_agent", DEFAULT_USER_AGENT)
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
