"""Constants for the AI Limits integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "ai_limits"

PLATFORMS = ["sensor", "binary_sensor"]

BASE_URL = "https://claude.ai"

PROVIDER_CLAUDE_WEB = "claude_web"
PROVIDER_GOOGLE_CA = "google_codeassist"
PROVIDER_ANTIGRAVITY = "antigravity"

PROVIDER_LABELS = {
    PROVIDER_CLAUDE_WEB: "Claude subscription (web session)",
    PROVIDER_GOOGLE_CA: "Google Gemini Code Assist (OAuth)",
    PROVIDER_ANTIGRAVITY: "Antigravity IDE (Google AI Pro)",
}

# Default window keys used before the first poll populates real ones.
WINDOW_KEYS = ["5h", "7d"]
WINDOW_LABELS = {
    "5h": "5-hour",
    "7d": "7-day",
    "7d_opus": "7-day Opus",
    "7d_sonnet": "7-day Sonnet",
    "7d_oi": "7-day OI",
    "7d_cowork": "7-day Cowork",
    "7d_oauth_apps": "7-day OAuth apps",
    "7d_omelette": "7-day Omelette",
}

# Config keys
CONF_PROVIDER = "provider"
CONF_ACCOUNT_NAME = "account_name"
CONF_COOKIE = "cookie"
CONF_USER_AGENT = "user_agent"
CONF_ORG_UUID = "org_uuid"
# Google OAuth token storage
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_GCP_PROJECT = "gcp_project"

# Options keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_PROBE = "enable_probe"
CONF_PROBE_MODEL = "probe_model"
CONF_DELETE_AFTER = "delete_after"

# Defaults
DEFAULT_SCAN_INTERVAL = 1800  # 30 min; usage changes slowly
MIN_SCAN_INTERVAL = 300
DEFAULT_ENABLE_PROBE = False
DEFAULT_DELETE_AFTER = True
DEFAULT_PROBE_MODEL = "claude-fable-5"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Status values
STATUS_OK = "ok"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"
