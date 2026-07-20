"""Wire models shared by the Code Assist providers (Gemini CLI + Antigravity).

Both talk to cloudcode-pa.googleapis.com/v1internal and share loadCodeAssist
and its tier/credit shapes. Provider-specific responses (retrieveUserQuota,
fetchAvailableModels) live in each provider's own models module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...models import as_float, get


@dataclass
class ClientMetadata:
    """metadata field for loadCodeAssist. Keys vary per client (camel vs snake)."""

    fields: dict[str, str] = field(
        default_factory=lambda: {"ideType": "GEMINI_CLI", "pluginType": "GEMINI"}
    )

    def to_dict(self) -> dict:
        return dict(self.fields)


@dataclass
class LoadCodeAssistRequest:
    metadata: ClientMetadata = field(default_factory=ClientMetadata)
    cloudaicompanionProject: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"metadata": self.metadata.to_dict()}
        if self.cloudaicompanionProject:
            d["cloudaicompanionProject"] = self.cloudaicompanionProject
        return d


@dataclass
class Credit:
    creditType: str | None = None
    creditAmount: str | None = None  # int64 as string
    minimumCreditAmountForUsage: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Credit:
        return cls(
            creditType=get(d, "creditType"),
            creditAmount=get(d, "creditAmount"),
            minimumCreditAmountForUsage=get(d, "minimumCreditAmountForUsage"),
        )


@dataclass
class GeminiUserTier:
    id: str | None = None  # 'free-tier' | 'standard-tier' | 'g1-pro-tier' | ...
    name: str | None = None
    availableCredits: list[Credit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict | None) -> GeminiUserTier | None:
        if not isinstance(d, dict):
            return None
        return cls(
            id=get(d, "id"),
            name=get(d, "name"),
            availableCredits=[
                Credit.from_dict(c) for c in (get(d, "availableCredits") or [])
            ],
        )

    @property
    def credits(self) -> Credit | None:
        return self.availableCredits[0] if self.availableCredits else None


@dataclass
class LoadCodeAssistResponse:
    currentTier: GeminiUserTier | None = None
    paidTier: GeminiUserTier | None = None
    allowedTiers: list[GeminiUserTier] = field(default_factory=list)
    cloudaicompanionProject: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> LoadCodeAssistResponse:
        return cls(
            currentTier=GeminiUserTier.from_dict(get(d, "currentTier")),
            paidTier=GeminiUserTier.from_dict(get(d, "paidTier")),
            allowedTiers=[
                t
                for t in (
                    GeminiUserTier.from_dict(x) for x in (get(d, "allowedTiers") or [])
                )
                if t is not None
            ],
            cloudaicompanionProject=get(d, "cloudaicompanionProject"),
        )

    def first_credit(self) -> Credit | None:
        for tier in (self.paidTier, self.currentTier, *self.allowedTiers):
            if tier is not None and tier.credits is not None:
                return tier.credits
        return None


def apply_credits(resp: LoadCodeAssistResponse, data) -> None:
    """Copy tier + credits from a loadCodeAssist response into LimitsData."""
    tier = resp.paidTier or resp.currentTier
    if tier is not None:
        data.plan = tier.name or tier.id
        data.tier = tier.id
    credit = resp.first_credit()
    if credit is not None:
        # proto3 omits a zero creditAmount; a present credit with no amount = 0.
        amount = as_float(credit.creditAmount)
        data.credits_available = amount if amount is not None else 0.0
        data.credits_min = as_float(credit.minimumCreditAmountForUsage)
