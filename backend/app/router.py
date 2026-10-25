"""Task -> Nemotron tier routing, plus cost accounting for the routing-savings metric."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Literal

from .config import settings

Tier = Literal["nano", "super", "ultra"]
Mode = Literal["routed", "ultra_only"]

TIER_ORDER: list[Tier] = ["nano", "super", "ultra"]

# Each agent task maps to the cheapest tier that handles it well. The reasons are shown
# in the UI's agent trace so users can see why a model was chosen.
TASK_ROUTES: dict[str, tuple[Tier, str]] = {
    "profile.extract": ("super", "Structured extraction from messy marketing pages"),
    "discover.queries": ("nano", "Short query generation from a known profile"),
    "discover.triage": ("nano", "High-volume yes/no relevance filter on search hits"),
    "discover.extract": ("nano", "Pull title, agency, dates, NAICS from an RFP page"),
    "discover.fit": ("ultra", "Multi-factor fit judgement drives what the user pursues"),
    "eligibility.requirements": ("super", "Long-document requirement extraction"),
    "eligibility.decide": ("ultra", "Dealbreaker reasoning: set-asides, bonding, clearances"),
    "draft.matrix": ("super", "Map every 'shall' statement to a response section"),
    "draft.statement": ("super", "Long-form grounded drafting"),
    "draft.review": ("ultra", "Final compliance review of the draft"),
}

_mode: ContextVar[Mode] = ContextVar("routing_mode", default="routed")


def set_mode(mode: Mode):
    """Set the routing mode for the current context; returns a token for reset()."""
    return _mode.set(mode)


def reset_mode(token) -> None:
    _mode.reset(token)


def current_mode() -> Mode:
    return _mode.get()


def route(task: str, escalate: int = 0) -> tuple[Tier, str]:
    """Return (tier, reason) for a task. `escalate` bumps the tier up N steps."""
    if current_mode() == "ultra_only":
        return "ultra", "Baseline mode: every call on Ultra"
    tier, reason = TASK_ROUTES.get(task, ("super", "Default tier for unlisted tasks"))
    if escalate:
        idx = min(TIER_ORDER.index(tier) + escalate, len(TIER_ORDER) - 1)
        if TIER_ORDER[idx] != tier:
            tier = TIER_ORDER[idx]
            reason = f"Escalated to {tier}: low confidence on cheaper tier"
    return tier, reason


def cost(tier: Tier, prompt_tokens: int, completion_tokens: int) -> float:
    """USD cost of a call at the configured per-1M-token prices."""
    price_in, price_out = settings.prices[tier]
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def savings(events: list[dict]) -> dict:
    """Compare actual cost against running the same tokens on Ultra."""
    llm = [e for e in events if e.get("kind") == "llm"]
    actual = sum(e.get("cost", 0.0) for e in llm)
    baseline = sum(cost("ultra", e.get("prompt_tokens", 0), e.get("completion_tokens", 0)) for e in llm)
    pct = (1 - actual / baseline) * 100 if baseline else 0.0
    by_tier: dict[str, int] = {}
    for e in llm:
        by_tier[e["tier"]] = by_tier.get(e["tier"], 0) + 1
    return {
        "actual_usd": round(actual, 6),
        "ultra_only_usd": round(baseline, 6),
        "saved_pct": round(pct, 1),
        "calls_by_tier": by_tier,
    }
