"""Gemini CLI Code Assist wire models: retrieveUserQuota."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ....models import WindowData, as_float, get, to_datetime


@dataclass
class RetrieveUserQuotaRequest:
    project: str | None = None

    def to_dict(self) -> dict:
        return {"project": self.project} if self.project else {}


@dataclass
class QuotaBucket:
    modelId: str | None = None
    tokenType: str | None = None
    remainingFraction: float | None = None
    remainingAmount: str | None = None
    resetTime: datetime | None = None

    @classmethod
    def from_dict(cls, d: dict) -> QuotaBucket:
        frac = as_float(get(d, "remainingFraction"))
        # proto3 omits zero-value floats -> absent means 0.0 (exhausted).
        if frac is None:
            frac = 0.0
        return cls(
            modelId=get(d, "modelId"),
            tokenType=get(d, "tokenType"),
            remainingFraction=frac,
            remainingAmount=get(d, "remainingAmount"),
            resetTime=to_datetime(get(d, "resetTime")),
        )

    @property
    def key(self) -> str:
        return self.modelId or self.tokenType or "unknown"

    def to_window_data(self) -> WindowData:
        used = (
            1.0 - self.remainingFraction
            if self.remainingFraction is not None
            else None
        )
        return WindowData(
            status="within_limit"
            if (self.remainingFraction is None or self.remainingFraction > 0)
            else "exhausted",
            utilization=used,
            resets_at=self.resetTime,
            label=self.key,
        )


@dataclass
class RetrieveUserQuotaResponse:
    buckets: list[QuotaBucket] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> RetrieveUserQuotaResponse:
        return cls(
            buckets=[QuotaBucket.from_dict(b) for b in (get(d, "buckets") or [])]
        )

    def to_windows(self) -> dict[str, WindowData]:
        windows: dict[str, WindowData] = {}
        for bucket in self.buckets:
            wd = bucket.to_window_data()
            existing = windows.get(bucket.key)
            if (
                existing is not None
                and existing.utilization is not None
                and (wd.utilization is None or wd.utilization <= existing.utilization)
            ):
                continue
            windows[bucket.key] = wd
        return windows
