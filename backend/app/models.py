"""Resolve Nemotron model IDs per tier from Token Factory's GET /v1/models."""
from __future__ import annotations

import logging

from .config import FALLBACK_MODELS, TIER_HINTS, settings

log = logging.getLogger(__name__)

_resolved: dict[str, str] | None = None


def pick_models(available: list[str]) -> dict[str, str]:
    """Pick one model ID per tier from a list of IDs, preferring the first matching hint."""
    lowered = {m.lower(): m for m in available}
    picked: dict[str, str] = {}
    for tier, hints in TIER_HINTS.items():
        for hint in hints:
            matches = sorted(orig for low, orig in lowered.items() if hint in low)
            # Skip vision/omni variants when a text model exists for the same tier.
            text_only = [m for m in matches if "omni" not in m.lower() and "vl" not in m.lower()]
            if text_only or matches:
                picked[tier] = (text_only or matches)[0]
                break
    return picked


def resolve_models(force: bool = False) -> dict[str, str]:
    """Return {tier: model_id}. Env overrides win, then /v1/models, then fallbacks."""
    global _resolved
    if _resolved is not None and not force:
        return _resolved

    found: dict[str, str] = {}
    if settings.has_llm:
        try:
            from .llm import client

            ids = [m.id for m in client().models.list().data]
            found = pick_models(ids)
            log.info("Resolved Nemotron models from /v1/models: %s", found)
        except Exception as exc:  # network or auth failure: fall back, don't crash startup
            log.warning("Could not list models (%s); using fallbacks", exc)

    _resolved = {
        tier: settings.model_overrides.get(tier) or found.get(tier) or FALLBACK_MODELS[tier]
        for tier in TIER_HINTS
    }
    return _resolved
