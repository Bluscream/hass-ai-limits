"""claude.ai web-session wire models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from typing import Any

from ....models import WindowData, as_float, get, to_datetime

# Normalised names for the top-level windows in the /usage response.
USAGE_WINDOW_NAMES = {
    "five_hour": "5h",
    "seven_day": "7d",
    "seven_day_opus": "7d_opus",
    "seven_day_sonnet": "7d_sonnet",
    "seven_day_cowork": "7d_cowork",
    "seven_day_oauth_apps": "7d_oauth_apps",
    "seven_day_omelette": "7d_omelette",
}
WINDOW_LABELS = {
    "5h": "5-hour",
    "7d": "7-day",
    "7d_opus": "7-day Opus",
    "7d_sonnet": "7-day Sonnet",
    "7d_cowork": "7-day Cowork",
    "7d_oauth_apps": "7-day OAuth apps",
    "7d_omelette": "7-day Omelette",
}
DEFAULT_WINDOW_KEYS = ["5h", "7d"]


@dataclass
class ClaudeOrganization:
    """GET /api/organizations/{org}."""

    uuid: str | None = None
    name: str | None = None
    capabilities: list[str] = field(default_factory=list)
    rate_limit_tier: str | None = None
    billing_type: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> ClaudeOrganization:
        return cls(
            uuid=get(d, "uuid"),
            name=get(d, "name"),
            capabilities=list(get(d, "capabilities") or []),
            rate_limit_tier=get(d, "rate_limit_tier"),
            billing_type=get(d, "billing_type"),
        )

    @property
    def plan(self) -> str:
        if "claude_max" in self.capabilities:
            return "claude_max"
        if "claude_pro" in self.capabilities:
            return "claude_pro"
        return "free"

    @property
    def is_chat_org(self) -> bool:
        return "chat" in self.capabilities


@dataclass
class UsageReport:
    """GET /api/organizations/{org}/usage.

    Windows are top-level keys (five_hour, seven_day, …) whose value is either
    ``null`` (inactive) or ``{utilization: <percent 0-100>, resets_at, ...}``.
    A ``limits`` array carries per-model scoped limits (e.g. "Weekly · Fable").
    """

    windows: dict[str, WindowData] = field(default_factory=dict)
    severity: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> UsageReport:
        windows: dict[str, WindowData] = {}
        if isinstance(d, dict):
            for raw_key, val in d.items():
                if not isinstance(val, dict):
                    continue
                if "utilization" not in val or "resets_at" not in val:
                    continue
                pct = as_float(val.get("utilization"))
                if pct is None:
                    continue
                key = USAGE_WINDOW_NAMES.get(raw_key, raw_key)
                windows[key] = WindowData(
                    status="exhausted" if pct >= 100 else "within_limit",
                    utilization=pct / 100.0,
                    resets_at=to_datetime(val.get("resets_at")),
                    label=WINDOW_LABELS.get(key),
                )

        severity = None
        for lim in get(d, "limits") or []:
            if not isinstance(lim, dict):
                continue
            if lim.get("severity") and lim.get("is_active"):
                severity = lim["severity"]
            scope_model = (lim.get("scope") or {}).get("model") or {}
            display = scope_model.get("display_name")
            if not display:
                continue
            group = lim.get("group") or "weekly"
            from ....models import slug as _slug

            key = f"{group}_{_slug(display)}"
            if key in windows:
                continue
            pct = as_float(lim.get("percent"))
            windows[key] = WindowData(
                status="exhausted" if (pct or 0) >= 100 else "within_limit",
                utilization=(pct / 100.0) if pct is not None else None,
                resets_at=to_datetime(lim.get("resets_at")),
                label=f"{group.title()} {display}",
            )
        return cls(windows=windows, severity=severity)

    @property
    def is_limited(self) -> bool:
        return any(w.is_exhausted for w in self.windows.values())


@dataclass
class MessageLimit:
    """The message_limit object from a completion SSE (active-probe fallback)."""

    windows: dict[str, WindowData] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> MessageLimit:
        windows: dict[str, WindowData] = {}
        for key, val in (get(d, "windows") or {}).items():
            if not isinstance(val, dict):
                continue
            frac = as_float(val.get("utilization"))
            norm = USAGE_WINDOW_NAMES.get(key, key)
            windows[norm] = WindowData(
                status=val.get("status"),
                utilization=frac,  # already a 0..1 fraction in the SSE
                resets_at=to_datetime(val.get("resets_at")),
                label=WINDOW_LABELS.get(norm),
            )
        return cls(windows=windows)

    @property
    def is_limited(self) -> bool:
        return any(w.is_exhausted for w in self.windows.values())


@dataclass
class CreateConversationParams:
    model: str
    name: str = "HA usage probe"
    include_conversation_preferences: bool = True
    paprika_mode: Any = None
    compass_mode: Any = None
    tool_search_mode: str = "auto"
    is_temporary: bool = True
    enabled_imagine: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompletionRequest:
    prompt: str
    model: str
    timezone: str = "UTC"
    locale: str = "en-US"
    effort: str = "low"
    thinking_mode: str = "off"
    rendering_mode: str = "messages"
    tools: list = field(default_factory=list)
    turn_message_uuids: dict = field(default_factory=dict)
    attachments: list = field(default_factory=list)
    files: list = field(default_factory=list)
    sync_sources: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["create_conversation_params"] = CreateConversationParams(
            model=self.model
        ).to_dict()
        return d
