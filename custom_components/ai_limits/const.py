"""Constants for the AI Limits integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "ai_limits"

PLATFORMS = ["sensor", "binary_sensor"]

# Default window keys used before the first poll populates real ones.
WINDOW_KEYS = ["5h", "7d"]

# Config keys
CONF_PROVIDER = "provider"
CONF_ACCOUNT_NAME = "account_name"

# Options keys
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL = 1800  # 30 min; usage changes slowly
MIN_SCAN_INTERVAL = 300

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Status values
STATUS_OK = "ok"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"
