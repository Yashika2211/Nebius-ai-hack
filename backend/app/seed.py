"""Seed the demo company and replay data so the golden path works without live keys.

- seed/demo_company.json: a fictional company described in owner notes, with a reviewed
  extraction (verified through the same grounding checks as live onboarding).
- seed/demo_cache.json (optional): recorded Token Factory + Tavily responses from a real
  live run, exported with `python -m app.seed export`. Replayed when keys are missing or
  a live call fails, so the demo never breaks in front of judges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import db, grounding
from .agents.profile import finalize

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"
DEMO_ID = "demo-ridgeline"


def demo_profile() -> dict:
    data = json.loads((SEED_DIR / "demo_company.json").read_text())
    spans = grounding.make_spans("notes", data["notes"])
    profile = finalize(data["extraction"], spans, data.get("website", ""), data["name"])
    profile["demo"] = True
    profile["notes"] = data["notes"]
    return profile


def load_cache() -> int:
    path = SEED_DIR / "demo_cache.json"
    if not path.exists():
        return 0
    entries = json.loads(path.read_text())
    for key, value in entries.items():
        if db.cache_get(key) is None:
            db.cache_put(key, value)
    return len(entries)


def load_snapshot() -> int:
    """Pre-recorded opportunities + analyses for the demo company."""
    path = SEED_DIR / "demo_snapshot.json"
    if not path.exists():
        return 0
    snap = json.loads(path.read_text())
    for opp in snap.get("opportunities", []):
        analyses = opp.pop("analyses", {})
        oid, is_new = db.upsert_opportunity(DEMO_ID, opp)
        if is_new:
            for kind, data in analyses.items():
                db.save_analysis(oid, kind, data)
    return len(snap.get("opportunities", []))


def ensure_seeded() -> None:
    if db.get_profile(DEMO_ID) is None:
        db.save_profile(demo_profile(), DEMO_ID)
    load_cache()
    load_snapshot()


def export() -> None:
    """Write the current cache and demo-company data to seed files."""
    with db.connect() as conn:
        rows = conn.execute("SELECT key, value FROM cache").fetchall()
    cache = {r["key"]: json.loads(r["value"]) for r in rows}
    (SEED_DIR / "demo_cache.json").write_text(json.dumps(cache))

    opps = []
    for opp in db.list_opportunities(DEMO_ID):
        opp.pop("first_seen", None)
        opp["analyses"] = {
            kind: a for kind in ("eligibility", "draft") if (a := db.latest_analysis(opp["id"], kind))
        }
        opps.append(opp)
    (SEED_DIR / "demo_snapshot.json").write_text(json.dumps({"opportunities": opps}, indent=1))
    print(f"Exported {len(cache)} cache entries and {len(opps)} demo opportunities")


if __name__ == "__main__":
    db.init()
    if sys.argv[1:] == ["export"]:
        export()
    else:
        ensure_seeded()
        print("Seeded demo company")
