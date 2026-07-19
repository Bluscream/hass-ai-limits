"""Sensor entities for AI Limits.

One sensor per usage window/model: its state is the utilization percentage,
with status, reset time, and countdown exposed as attributes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import AILimitsConfigEntry
from .const import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_UNKNOWN,
    WINDOW_KEYS,
    WINDOW_LABELS,
)
from .entity import AILimitsEntity
from .models import LimitsData, WindowData


@dataclass(frozen=True, kw_only=True)
class AILimitsSensorDescription(SensorEntityDescription):
    """Describes an AI Limits sensor."""

    value_fn: Callable[[LimitsData], StateType | datetime]
    attr_fn: Callable[[LimitsData], dict] | None = None


def _window(data: LimitsData, key: str) -> WindowData | None:
    return data.windows.get(key)


def _fmt_duration(seconds: float) -> str:
    s = max(0, int(seconds))
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, _ = divmod(s, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return "<1m"


def _window_reset_in(win: WindowData) -> int | None:
    if win.resets_at is None:
        return None
    return max(0, round((win.resets_at - dt_util.utcnow()).total_seconds()))


def _window_state(data: LimitsData, key: str) -> str | None:
    """Human-readable summary.

    Normally '25% remaining'. Only once the window is fully used up does it
    switch to 'Resets in 1h 20m'.
    """
    win = _window(data, key)
    if win is None:
        return None
    reset_in = _window_reset_in(win)
    if win.utilization is not None:
        remaining = round(100 - win.utilization * 100)
        exhausted = remaining <= 0 or win.is_exhausted
        if exhausted:
            if reset_in:
                return f"Resets in {_fmt_duration(reset_in)}"
            return "0% remaining"
        return f"{remaining}% remaining"
    # Utilization unknown: fall back to reset time if we have it.
    if reset_in:
        return f"Resets in {_fmt_duration(reset_in)}"
    return None


def _window_attrs(data: LimitsData, key: str) -> dict:
    win = _window(data, key)
    if win is None:
        return {}
    used = round(win.utilization * 100, 1) if win.utilization is not None else None
    return {
        "status": win.status,
        "group": win.group,
        "utilization_percent": used,
        "remaining_percent": round(100 - used, 1) if used is not None else None,
        "resets_at": win.resets_at.isoformat() if win.resets_at else None,
        "resets_in_seconds": _window_reset_in(win),
    }


def _base_descriptions() -> list[AILimitsSensorDescription]:
    return [
        AILimitsSensorDescription(
            key="status",
            name="Status",
            icon="mdi:account-key",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.ENUM,
            options=[STATUS_OK, STATUS_RATE_LIMITED, STATUS_ERROR, STATUS_UNKNOWN],
            value_fn=lambda d: d.status,
            attr_fn=lambda d: {
                "error": d.error,
                "plan": d.plan,
                "tier": d.tier,
                **d.raw,
            },
        ),
        AILimitsSensorDescription(
            key="cooldown",
            name="Soonest reset in",
            icon="mdi:timer-sand",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="s",
            value_fn=lambda d: (
                round(d.retry_after)
                if d.retry_after is not None
                else (round(d.reset_in) if d.reset_in is not None else None)
            ),
        ),
        AILimitsSensorDescription(
            key="markdown_card",
            name="Markdown Card",
            icon="mdi:card-text",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda d: len(d.windows) if d else 0,
        ),
    ]


def _window_description(key: str, label: str) -> AILimitsSensorDescription:
    return AILimitsSensorDescription(
        key=key,
        name=label,
        icon="mdi:gauge",
        value_fn=lambda d, k=key: _window_state(d, k),
        attr_fn=lambda d, k=key: _window_attrs(d, k),
    )


_CREDITS_DESCRIPTION = AILimitsSensorDescription(
    key="credits",
    name="AI Credits",
    icon="mdi:cash",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="credits",
    suggested_display_precision=0,
    value_fn=lambda d: (
        int(d.credits_available) if d.credits_available is not None else None
    ),
    attr_fn=lambda d: {
        "minimum_for_usage": (
            int(d.credits_min) if d.credits_min is not None else None
        )
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AILimitsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for one account.

    Window keys are provider-specific (Claude: 5h/7d/…; Google: per model), so
    they are derived from the first poll's data. Reload the entry to pick up
    windows that appear later.
    """
    coordinator = entry.runtime_data
    data = coordinator.data
    windows = data.windows if data else {}
    window_keys = list(windows.keys())
    if not window_keys and coordinator.provider_id == "claude_web":
        window_keys = WINDOW_KEYS

    def _label(key: str) -> str:
        win = windows.get(key)
        if win is not None and win.label:
            return win.label
        return WINDOW_LABELS.get(key, key)

    descriptions = _base_descriptions()
    descriptions += [_window_description(key, _label(key)) for key in window_keys]
    if data is not None and data.credits_available is not None:
        descriptions.append(_CREDITS_DESCRIPTION)

    async_add_entities(AILimitsSensor(coordinator, desc) for desc in descriptions)


class AILimitsSensor(AILimitsEntity, SensorEntity):
    """A single limit metric for one account."""

    entity_description: AILimitsSensorDescription

    def __init__(self, coordinator, description: AILimitsSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key == "markdown_card":
            return {"markdown": self._generate_markdown_card()}
        if self.entity_description.attr_fn is None:
            return None
        return {
            k: v
            for k, v in self.entity_description.attr_fn(self.coordinator.data).items()
            if v is not None
        }

    def _generate_markdown_card(self) -> str:
        """Generate Lovelace Markdown card content showing all accounts."""
        lines = []
        entries = self.hass.config_entries.async_entries("ai_limits")
        for entry in entries:
            coordinator = getattr(entry, "runtime_data", None)
            if not coordinator or not coordinator.data:
                continue

            data = coordinator.data
            provider = entry.data.get("provider")

            provider_name = "Claude AI" if provider == "claude_web" else "Google AI"
            account_name = entry.title

            header = f"- **{provider_name} ({account_name})**"
            if data.credits_available is not None:
                credits_val = int(data.credits_available)
                header += f" (🪙 {credits_val})"

            lines.append(header)

            for key, win in data.windows.items():
                status = win.status
                emoji = "🔴" if status == "exhausted" else "🟢"

                label = win.label or WINDOW_LABELS.get(key, key)

                state_str = "Unknown"
                reset_in = _window_reset_in(win)
                if win.utilization is not None:
                    remaining = round(100 - win.utilization * 100)
                    exhausted = remaining <= 0 or win.is_exhausted
                    if exhausted:
                        if reset_in:
                            state_str = f"Resets in {_fmt_duration(reset_in)}"
                        else:
                            state_str = "0% remaining"
                    else:
                        state_str = f"{remaining}% remaining"
                elif reset_in:
                    state_str = f"Resets in {_fmt_duration(reset_in)}"

                lines.append(f"  - {emoji} {label}: {state_str}")

            lines.append("")

        return "\n".join(lines).strip()
