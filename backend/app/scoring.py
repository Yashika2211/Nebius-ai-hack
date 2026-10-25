"""Transparent fit score: the model scores factors, code combines them with fixed weights."""
from __future__ import annotations

FACTORS: dict[str, dict] = {
    "naics_match": {"label": "NAICS code / industry match", "weight": 0.20},
    "capability_match": {"label": "Specific capability match to the scope of work", "weight": 0.30},
    "set_aside_eligibility": {"label": "Eligible for the set-aside (or full and open)", "weight": 0.20},
    "past_performance": {"label": "Relevant past performance of similar size/scope", "weight": 0.15},
    "location_feasibility": {"label": "Place of performance is serviceable", "weight": 0.10},
    "deadline_feasibility": {"label": "Enough time to prepare a response", "weight": 0.05},
}


def deadline_score(days_left: int | None) -> float | None:
    """Deterministic deadline score; None means let the model's score stand."""
    if days_left is None:
        return None
    if days_left < 0:
        return 0.0
    if days_left < 5:
        return 3.0
    if days_left < 10:
        return 6.0
    return 10.0


def combine(factors: dict[str, dict], days_left: int | None = None) -> dict:
    """Weighted 0-100 score. Expired solicitations score 0 regardless of fit."""
    ds = deadline_score(days_left)
    if ds is not None and "deadline_feasibility" in factors:
        factors["deadline_feasibility"] = {
            **factors["deadline_feasibility"],
            "score": ds,
            "reason": f"{days_left} days until the response is due" if days_left >= 0 else "Deadline has passed",
            "grounded": True,  # computed from the extracted due date, not model reasoning
            "evidence": [],
        }

    total, breakdown = 0.0, []
    for key, meta in FACTORS.items():
        f = factors.get(key, {})
        try:
            s = max(0.0, min(10.0, float(f.get("score", 0))))
        except (TypeError, ValueError):
            s = 0.0
        # An unsupported justification counts for half: we don't fully trust ungrounded reasoning.
        grounded = f.get("grounded", True)
        effective = s if grounded else s * 0.5
        total += effective * meta["weight"] * 10
        breakdown.append({
            "key": key,
            "label": meta["label"],
            "weight": meta["weight"],
            "score": s,
            "grounded": grounded,
            "reason": f.get("reason", ""),
            "evidence": f.get("evidence", []),
        })

    score = round(total)
    if days_left is not None and days_left < 0:
        score = 0
    if factors.get("set_aside_eligibility", {}).get("score", 10) == 0:
        score = min(score, 20)  # ineligible for the set-aside is a dealbreaker
    band = "strong" if score >= 75 else "possible" if score >= 50 else "weak"
    return {"score": score, "band": band, "factors": breakdown}
