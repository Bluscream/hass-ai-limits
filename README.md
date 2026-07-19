# AI Limits

A Home Assistant custom integration that surfaces **AI subscription usage limits**
as devices/entities — how much of each rolling window you've used, and when it
resets.

One account = one config entry = one device. Adding multiple accounts across different providers is fully supported.

| Provider | What it reads | Auth Options | Cost per poll |
|---|---|---|---|
| **Claude subscription (web session)** | Claude Pro/Max usage windows (5h, 7d, per-model 7d) | Browser session cookie | None (passive) |
| **Claude API Token** | Anthropic developer organization messages usage | Anthropic Admin API key | None (passive) |
| **Google One Subscription (Google)** | Antigravity quota groups (Gemini, Claude, GPT) + AI Credits | Google OAuth | None (passive) |
| **Gemini API Token** | Google AI Studio developer API quotas | Google OAuth | None (passive) |
| **Devin** | Devin organization spending state and session limits | Google OAuth / GitHub OAuth / Bearer Token | None (passive) |
| **ChatGPT Subscription** | ChatGPT Plus/Team usage limits (Stub) | Browser session cookie | None (passive) |
| **ChatGPT API Token** | OpenAI Platform developer usage and spend (Stub) | OpenAI Admin API key | None (passive) |
| **DeepSeek API Token** | DeepSeek Developer API balance | DeepSeek API key | None (passive) |
| **OpenRouter API Token** | OpenRouter Developer API credit limit and remaining balance | OpenRouter API key | None (passive) |

> ⚠️ **Unofficial.** This talks to private and public endpoints of `claude.ai`, `devin.ai`, and Google's Code Assist APIs using your own credentials. It can break at any time if either provider changes things.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Click the three dots (⋮) in the top right corner and select **Custom repositories**.
3. Add Repository URL: `https://github.com/Bluscream/hass-ai-limits`
4. Type: **Integration**
5. Click **Add**, then find and install **AI Limits**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/ai_limits` folder into `<config>/custom_components/`.
2. Restart Home Assistant.

### Configuration

1. Go to **Settings → Devices & Services → Add Integration → "AI Limits"**.
2. Pick a provider from the menu. Add the integration again to track additional accounts.

---

## Lovelace Dashboard Card

This integration includes a custom dashboard card that dynamically gathers all configured Claude/Google AI/Devin accounts and lists their limits with a progress bar. 

```yaml
type: custom:ai-limits-card
title: "AI Limits"             # Optional (omit or set to "" to hide card header)
icon: "mdi:gauge"              # Optional (omit or set to "" to hide icon)
show_header: true              # Optional (set to false to fully omit the header)
ok_color: "#2ecc71"            # Optional (custom color for active limits)
exhausted_color: "#e74c3c"     # Optional (primary stripe color for exhausted limits)
exhausted_bg_color: "#7f8c8d"  # Optional (secondary stripe color for exhausted limits)
```

---

## Automation Blueprint

The integration automatically installs a notification blueprint to your local Home Assistant instance on startup: `blueprints/automation/ai_limits/ai_limits_reset_notification.yaml`.

This blueprint allows you to easily set up notifications on your devices (including your PC/ntfy) when a limit resets, triggering **only if the limit was fully exhausted/used up** beforehand.
