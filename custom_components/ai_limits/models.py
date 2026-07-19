"""Shared, provider-agnostic models and parsing helpers.

Provider-specific request/response schemas live in each provider package
(providers/<name>/models.py). This module holds only what every provider
normalises to: WindowData / LimitsData, OAuth tokens, and small parse helpers.
No Home Assistant dependency, so it can be unit-tested in isolation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Parsing helpers (shared by every provider's models)
# ---------------------------------------------------------------------------


def get(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, dict) else default


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def slug(name: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in name.lower())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _parse_iso(value: str) -> datetime | None:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_datetime(value: Any) -> datetime | None:
    """Coerce an epoch (s or ms), numeric string, or ISO-8601 string to UTC."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        if num > 1e12:  # milliseconds
            num /= 1000
        if num > 1_000_000_000:
            return datetime.fromtimestamp(num, tz=timezone.utc)
        return None
    if isinstance(value, str):
        num = as_float(value)
        if num is not None:
            return to_datetime(num)
        return _parse_iso(value)
    return None


# ---------------------------------------------------------------------------
# Normalised model (what the coordinator + entities consume)
# ---------------------------------------------------------------------------


@dataclass
class WindowData:
    """One normalised usage window (utilization as a 0..1 fraction used)."""

    status: str | None = None
    utilization: float | None = None  # 0..1, fraction *used*
    resets_at: datetime | None = None
    label: str | None = None  # display name override for the entity
    group: str | None = None  # provider group (e.g. "Gemini", "Claude & GPT")

    @property
    def is_exhausted(self) -> bool:
        return self.status not in (None, "within_limit", "ok")


@dataclass
class LimitsData:
    """Provider-agnostic snapshot handed to the coordinator."""

    status: str = "unknown"
    error: str | None = None
    plan: str | None = None
    tier: str | None = None

    windows: dict[str, WindowData] = field(default_factory=dict)

    retry_after: float | None = None
    reset_in: float | None = None

    # Overage / prepaid credits (e.g. Antigravity "AI Credits").
    credits_available: float | None = None
    credits_min: float | None = None

    raw: dict = field(default_factory=dict)

    def recompute_reset_in(self, now: datetime) -> None:
        soonest: float | None = None
        for win in self.windows.values():
            if win.resets_at is None:
                continue
            secs = max(0.0, (win.resets_at - now).total_seconds())
            soonest = secs if soonest is None else min(soonest, secs)
        self.reset_in = soonest

    def update_window(
        self,
        label: str,
        used: float,
        limit: float,
        window_seconds: float,
        group: str | None = None,
    ) -> None:
        """Convenience: add/update a WindowData by label from raw used/limit counts.

        utilization = used / limit (clamped 0..1).
        resets_at is not set (providers that need it build WindowData directly).
        """
        key = slug(label)
        utilization = min(1.0, used / limit) if limit else 0.0
        status = "within_limit" if utilization < 1.0 else "rate_limited"
        self.windows[key] = WindowData(
            status=status,
            utilization=utilization,
            label=label,
            group=group,
        )


# ---------------------------------------------------------------------------
# OAuth (shared by all OAuth providers)
# ---------------------------------------------------------------------------


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float

    @classmethod
    def from_response(cls, payload: dict) -> OAuthTokens:
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + float(payload.get("expires_in", 3600)),
        )

    def to_storage(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60
