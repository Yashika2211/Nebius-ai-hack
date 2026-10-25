"""Watch mode: re-run discovery for saved profiles and record newly seen opportunities.

Run on a schedule with `python -m app.watch` (cron, GitHub Actions, or a serverless job),
or trigger via POST /api/watch/run.
"""
from __future__ import annotations

import logging
import sys

from . import db, trace
from .agents.discover import discover

log = logging.getLogger(__name__)


def run_for_profile(profile: dict) -> list[dict]:
    own_trace = trace.current() is None
    t = trace.start(f"watch:{profile.get('name')}") if own_trace else trace.current()
    opps = discover(profile, max_opps=5)
    new_items = []
    for opp in opps:
        oid, is_new = db.upsert_opportunity(profile["id"], opp)
        if is_new:
            new_items.append({"id": oid, "title": opp.get("title"), "url": opp.get("url"),
                              "score": opp["fit"]["score"], "due_date": opp.get("due_date")})
    db.save_watch_run(profile["id"], new_items)
    if own_trace:
        t.finish()
    return new_items


def run_all() -> dict[str, int]:
    db.init()
    results = {}
    for profile in db.list_profiles():
        try:
            results[profile["id"]] = len(run_for_profile(profile))
        except Exception as exc:  # one broken profile shouldn't stop the others
            log.exception("Watch failed for %s: %s", profile.get("id"), exc)
            results[profile["id"]] = -1
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = run_all()
    print(out)
    sys.exit(0 if all(v >= 0 for v in out.values()) else 1)
