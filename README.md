# AI Limits

A Home Assistant custom integration that surfaces **AI subscription usage limits**
as devices/entities — how much of each rolling window you've used, and when it
resets.

Two account types are supported, each added separately (one config entry =
one account = one device):

| Provider | What it reads | Auth | Cost per poll |
|---|---|---|---|
| **Claude subscription (web session)** | Your Claude Pro/Max usage windows (5h, 7d, and per-model 7d) | Browser session cookie | None (passive) |
| **Google Gemini Code Assist (OAuth)** | Per-model Code Assist quota (the backend Antigravity / gemini-cli use) | Google OAuth | None (passive) |

> ⚠️ **Unofficial.** This talks to private endpoints of claude.ai and Google's
> Code Assist API using your own credentials. It can break at any time if either
> provider changes things, and it may be against their Terms of Service. Use it
> only with your own accounts.

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

## Provider 1 — Claude subscription (web session)

Reads your Claude subscription usage from `claude.ai` using your logged-in
browser session — via the same **passive** `GET /api/organizations/{org}/usage`
endpoint the **Claude desktop app** polls. No messages are sent.

> Claude Desktop and the website share the **same** subscription/account, so
> this is your full subscription usage, including what the desktop's Claude
> Code / cowork features consume.

### Getting the cookie

1. Sign in at <https://claude.ai> in a normal browser.
2. Open **DevTools (F12) → Network** tab.
3. Click any request to `claude.ai` (e.g. reload the page and pick one).
4. Under **Request Headers**, copy the **entire `Cookie` header** value.
   - It must include `sessionKey` and `cf_clearance`.
5. Note the **`User-Agent`** header from the same request.

### Adding it

- **Account name** — a label (e.g. `personal`).
- **Cookie header** — paste the whole cookie string (stored masked).
- **User-Agent** — must match the browser you copied the cookie from, or
  Cloudflare may block the request. A Chrome default is pre-filled.

### When the cookie expires

`cf_clearance` lasts hours–days; `sessionKey` lasts longer. When it lapses the
integration goes to an auth error and Home Assistant prompts you to **reauth** —
just paste a fresh `Cookie` header.

### Active-probe fallback (optional)

If the passive `/usage` endpoint ever returns nothing for your account, enable
**Configure → “Enable active probe fallback”**. This sends a tiny throwaway
message (temporary conversation, cheapest model, auto-deleted) each poll to read
the usage windows from the completion response. It consumes a small amount of
quota, so it stays **off** by default.

---

## Provider 2 — Google Gemini Code Assist (OAuth)

Reads your **Gemini Code Assist** quota from `cloudcode-pa.googleapis.com` — the
same backend Antigravity and gemini-cli use. This is passive (no prompts) and
returns real per-model `remainingFraction` + reset times.

> This is the **Code Assist** quota (Google login coding tier), **not** the
> gemini.google.com app — that app exposes no usage data anywhere.

### Adding it

1. Choose **Google Gemini Code Assist (OAuth)**.
2. Open the sign-in URL shown in the form and authorize with your Google
   account.
3. The page then displays an **authorization code**. Copy it.
4. Paste the code plus an **account name** into the form.

Tokens are stored and **auto-refreshed**. If they ever lapse, reauth re-runs the
grant.

> Your Google account must already be onboarded to Code Assist (it is if you've
> used Antigravity or gemini-cli). A brand-new account may need a one-time
> onboarding in one of those tools first.

---

## Entities

Each account becomes a **device** with:

| Entity | Notes |
|---|---|
| **Status** (sensor, enum) | `ok` / `rate_limited` / `error` / `unknown`. Attributes include `plan`, `tier`, error detail, and raw payload. |
| **Rate limited** (binary sensor) | On when any window is at its limit. |
| **Soonest reset in** (sensor, seconds) | Countdown to the nearest window reset. |
| **`<window>` utilization** (sensor, %) | Per window/model. Claude: `5-hour`, `7-day`, and per-model 7d (opt-in). Google: one per model id. |
| **`<window>` resets at** (sensor, timestamp) | When that window resets. |

Window entities are created from the **first successful poll**. If new windows
appear later (e.g. a per-model limit becomes active), **reload the entry** to
add their entities.

---

## Options (the “Configure” button)

- **Poll interval** — seconds between updates (Claude default 30 min, min 5 min;
  usage changes slowly).
- **Claude only:** active-probe fallback toggle, delete-probe-conversation
  toggle, and probe model.

---

## Troubleshooting

- **Claude Status = error, `invalid_auth`** — cookie expired or Cloudflare
  blocked it. Reauth with a fresh cookie and make sure the User-Agent matches.
- **Claude utilization sensors empty but Status = ok** — the `/usage` endpoint
  returned an unrecognized shape. Check the Status sensor's `usage_payload`
  attribute; that's the raw response for mapping.
- **Google Status = error after a while** — token refresh failed; reauth.
- **Google Status = rate_limited constantly** — you're actually out of Code
  Assist quota (the `RESOURCE_EXHAUSTED` state); it clears at the reset time.

---

## Lovelace Dashboard Card

This integration includes a custom dashboard card that dynamically gathers all configured Claude/Google AI accounts and lists their limits with a progress bar. 

### Adding the Card:
1. Go to your dashboard and select **Edit Dashboard**.
2. Click **Add Card**.
3. Search for and choose **AI Limits Card** (or add `type: custom:ai-limits-card` in YAML mode).

- **Active limits** display as a green progress bar showing the remaining percentage.
- **Exhausted limits** display as an animated red/gray striped bar showing progress towards reset.

---

## Automation Blueprint

The integration automatically installs a notification blueprint to your local Home Assistant instance on startup: `blueprints/automation/ai_limits/ai_limits_reset_notification.yaml`.

This blueprint allows you to easily set up notifications on your devices (including your PC/ntfy) when a limit resets, triggering **only if the limit was fully exhausted/used up** beforehand.

### Setting it up:
1. Go to **Settings → Automations & Scenes → Blueprints**.
2. Find **AI Limits Reset Notification** and click **Create Automation**.
3. Select the utilization sensors you want to monitor, your target notification script (expects `script.notify` interface), and the target severity/scope (e.g. `blu`).

---

## How it works (endpoints)

- Claude: `GET /api/organizations/{org}` (plan/tier),
  `GET /api/organizations/{org}/usage` (windows, passive),
  `POST …/chat_conversations/{id}/completion` (probe fallback only).
- Google: `POST /v1internal:loadCodeAssist` (tier),
  `POST /v1internal:retrieveUserQuota` (per-model quota buckets).

Nothing leaves your Home Assistant instance except the direct calls to
claude.ai / Google with your own credentials.
