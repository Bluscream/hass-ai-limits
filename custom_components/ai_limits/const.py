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
CONF_GCP_PROJECT = "gcp_project"

# Options keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_PROBE = "enable_probe"
CONF_DELETE_AFTER = "delete_after_probe"
CONF_PROBE_MODEL = "probe_model"

# Defaults
DEFAULT_SCAN_INTERVAL = 1800  # 30 min; usage changes slowly
MIN_SCAN_INTERVAL = 300
DEFAULT_ENABLE_PROBE = False
DEFAULT_DELETE_AFTER = False
DEFAULT_PROBE_MODEL = "claude-3-5-haiku-20241022"

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Status values
STATUS_OK = "ok"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"
