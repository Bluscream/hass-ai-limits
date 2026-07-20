"""Antigravity-specific wire models: fetchAvailableModels + onboardUser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ....models import WindowData, as_float, get, slug, to_datetime

# Map the API's modelProvider to the UI's quota groups.
MODEL_GROUPS = {
    "MODEL_PROVIDER_GOOGLE": "Gemini",
    "MODEL_PROVIDER_ANTHROPIC": "Claude & GPT",
    "MODEL_PROVIDER_OPENAI": "Claude & GPT",
}


@dataclass
class ModelQuota:
    """One model entry from fetchAvailableModels."""

    model_id: str
    display_name: str | None = None
    provider: str | None = None
    remaining_fraction: float | None = None
    resets_at: datetime | None = None

    @classmethod
    def from_dict(cls, model_id: str, d: dict) -> ModelQuota:
        qi = d.get("quotaInfo") or {}
        # proto3 omits zero-value floats: absent remainingFraction == 0.0.
        frac = as_float(qi.get("remainingFraction"))
        if frac is None:
            frac = 0.0
        return cls(
            model_id=model_id,
            display_name=d.get("displayName"),
            provider=d.get("modelProvider"),
            remaining_fraction=frac,
            resets_at=to_datetime(qi.get("resetTime")),
        )

    @property
    def group(self) -> str:
        return MODEL_GROUPS.get(self.provider or "", "Other")


@dataclass
class FetchAvailableModelsResponse:
    models: list[ModelQuota] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> FetchAvailableModelsResponse:
        raw_models = get(d, "models") or {}
        return cls(
            models=[
                ModelQuota.from_dict(mid, m)
                for mid, m in raw_models.items()
                if isinstance(m, dict)
            ]
        )

    def to_windows(self) -> dict[str, WindowData]:
        """Collapse models into per-group windows (worst/binding quota wins)."""
        groups: dict[str, list[ModelQuota]] = {}
        for m in self.models:
            if m.resets_at is None:
                continue  # internal/tab models carry no user quota
            groups.setdefault(m.group, []).append(m)

        windows: dict[str, WindowData] = {}
        for group, members in groups.items():
            worst = min(
                members,
                key=lambda x: x.remaining_fraction
                if x.remaining_fraction is not None
                else 0.0,
            )
            frac = worst.remaining_fraction
            windows[slug(group)] = WindowData(
                status="exhausted" if (frac or 0) <= 0 else "within_limit",
                utilization=(1 - frac) if frac is not None else None,
                resets_at=worst.resets_at,
                label=group,
                group=group,
            )
        return windows


def onboard_project(payload: dict) -> str | None:
    """Pull the cloudaicompanionProject id out of an onboardUser response."""
    return (
        (get(payload, "response") or {})
        .get("cloudaicompanionProject", {})
        .get("id")
    )
