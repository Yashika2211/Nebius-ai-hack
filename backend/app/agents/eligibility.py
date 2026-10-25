"""Eligibility and risk agent: extract requirements, decide met/not met, flag dealbreakers."""
from __future__ import annotations

import re

from .. import grounding, llm, trace
from .discover import days_until, profile_spans

CATEGORIES = [
    "set_aside", "size_standard", "naics", "clearance", "bonding", "insurance", "license",
    "experience", "location", "deadline", "submission", "other",
]

REQ_SYSTEM = """You extract eligibility and qualification requirements from a government
solicitation. Focus on things that can disqualify a bidder: set-asides, size standards,
NAICS, security clearances, bonding, insurance minimums, licenses, required years or dollar
value of experience, on-site/location requirements, deadlines, mandatory submission items.
Each requirement cites RFP span IDs with a short verbatim quote (under 25 words).

Return JSON: {"requirements": [{"id": "R1", "category": one of """ + "|".join(CATEGORIES) + """,
"text": str (plain-language requirement), "mandatory": bool, "citations": [ids], "quote": str}]}
List at most 15, most disqualifying first."""

DECIDE_SYSTEM = """You decide whether a small business meets each solicitation requirement,
using ONLY its profile spans (profile:N). Be conservative:
- "met": the profile explicitly shows it (cite profile span + quote)
- "not_met": the profile shows it can't be met, or a set-aside certification is missing
- "unknown": the profile doesn't say (e.g. bonding capacity not listed)
A requirement is a dealbreaker when it is mandatory and not_met.

Return JSON: {"decisions": [{"id": "R1", "status": "met|not_met|unknown", "dealbreaker": bool,
"explanation": str (one sentence), "action": str (what the owner should do, one sentence),
"citations": [profile ids], "quote": str}],
"verdict": "go|caution|no_go", "verdict_reason": str (one sentence)}"""

SET_ASIDE_CERTS = {
    "8(a)": ["8(a)"],
    "hubzone": ["HUBZone"],
    "wosb": ["WOSB", "EDWOSB"],
    "edwosb": ["EDWOSB"],
    "sdvosb": ["SDVOSB"],
    "service-disabled": ["SDVOSB"],
    "veteran": ["VOSB", "SDVOSB"],
}


def set_aside_check(set_aside: str | None, profile: dict) -> dict | None:
    """Deterministic set-aside eligibility so the most common dealbreaker never hinges on a model."""
    if not set_aside:
        return None
    sa = set_aside.lower()
    held = {c.get("name", "").upper() for c in profile.get("certifications", [])}
    for needle, certs in SET_ASIDE_CERTS.items():
        if needle in sa:
            ok = any(c.upper() in held for c in certs)
            return {"set_aside": set_aside, "required": certs, "eligible": ok}
    if re.search(r"small business|total small|sb set", sa):
        return {"set_aside": set_aside, "required": ["small business size standard"], "eligible": None}
    return None


def check(profile: dict, opp: dict) -> dict:
    rfp = grounding.make_spans("rfp", opp.get("source_text", "")[:40000], url=opp.get("url", ""))
    prof = profile_spans(profile)

    trace.step("Requirements", "Extracting disqualifying requirements from the RFP")
    reqs = llm.chat_json("eligibility.requirements", REQ_SYSTEM, grounding.render(rfp, 20000),
                         max_tokens=2500).get("requirements", [])
    reqs = grounding.verify_claims(reqs, rfp)

    trace.step("Eligibility decision", f"Checking {len(reqs)} requirements against your profile")
    listing = "\n".join(f"{r['id']} [{r.get('category')}] {'MANDATORY ' if r.get('mandatory') else ''}{r.get('text')}"
                        for r in reqs)
    raw = llm.chat_json(
        "eligibility.decide",
        DECIDE_SYSTEM,
        f"PROFILE:\n{grounding.render(prof, 6000)}\n\nREQUIREMENTS:\n{listing}",
        max_tokens=2500,
    )
    decisions = {d.get("id"): d for d in grounding.verify_claims(raw.get("decisions", []), prof)}

    items = []
    for r in reqs:
        d = decisions.get(r["id"], {"status": "unknown", "explanation": "Not assessed", "dealbreaker": False})
        # A "met" decision without profile evidence is downgraded: we can't show proof.
        status = d.get("status", "unknown")
        if status == "met" and not d.get("grounded"):
            status = "unknown"
        items.append({
            "requirement": r,
            "status": status,
            "dealbreaker": bool(d.get("dealbreaker")) and status == "not_met",
            "explanation": d.get("explanation", ""),
            "action": d.get("action", ""),
            "profile_evidence": d.get("evidence", []),
        })

    sa = set_aside_check(opp.get("set_aside"), profile)
    if sa and sa["eligible"] is False:
        items.insert(0, {
            "requirement": {"id": "SA", "category": "set_aside", "text": f"Set-aside: {sa['set_aside']}",
                            "mandatory": True, "grounded": True, "evidence": []},
            "status": "not_met",
            "dealbreaker": True,
            "explanation": f"Requires {' or '.join(sa['required'])} certification, which is not in your profile.",
            "action": "Only pursue as a subcontractor to a certified prime, or get certified.",
            "profile_evidence": [],
        })

    days = days_until(opp.get("due_date"))
    if days is not None and days < 0:
        items.insert(0, {
            "requirement": {"id": "DL", "category": "deadline", "text": f"Responses due {opp.get('due_date')}",
                            "mandatory": True, "grounded": True, "evidence": []},
            "status": "not_met", "dealbreaker": True,
            "explanation": "The response deadline has passed.", "action": "Watch for a re-solicitation.",
            "profile_evidence": [],
        })

    dealbreakers = [i for i in items if i["dealbreaker"]]
    unknowns = [i for i in items if i["status"] == "unknown"]
    verdict = "no_go" if dealbreakers else "caution" if unknowns else "go"
    trace.emit({"kind": "check", "name": "eligibility",
                "detail": f"{len(dealbreakers)} dealbreakers, {len(unknowns)} unknowns → {verdict}"})
    return {
        "verdict": verdict,
        "verdict_reason": raw.get("verdict_reason", ""),
        "model_verdict": raw.get("verdict"),
        "days_left": days,
        "set_aside": sa,
        "items": items,
        "counts": {
            "met": sum(1 for i in items if i["status"] == "met"),
            "not_met": sum(1 for i in items if i["status"] == "not_met"),
            "unknown": len(unknowns),
            "dealbreakers": len(dealbreakers),
        },
    }
