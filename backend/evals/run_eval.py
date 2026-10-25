"""Routed vs. Ultra-only evaluation on hand-labeled real solicitations.

Each file in evals/rfps/*.json is one solicitation:
  {"id", "url", "text", "labels": {"set_aside", "naics", "due_date", "eligible", "fit"}}
`eligible` is whether the demo company can bid; `fit` is strong|possible|weak.

For each RFP and each mode we run the pipeline steps that touch it (extract -> fit ->
eligibility) and compare to labels. Usage:
  python -m evals.run_eval            # both modes, writes evals/results.md + results.json
  python -m evals.run_eval --mode routed
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, router, seed, trace  # noqa: E402
from app.agents import eligibility  # noqa: E402
from app.agents.discover import extract_opportunity, score_fit  # noqa: E402

HERE = Path(__file__).resolve().parent


def load_rfps() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((HERE / "rfps").glob("*.json"))]


def norm(s) -> str:
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def set_aside_match(pred, gold) -> bool:
    """Compare set-asides by the certification they require (or none)."""
    keys = ["8a", "hubzone", "edwosb", "wosb", "sdvosb", "servicedisabled", "veteran", "smallbusiness"]
    find = lambda s: next((k for k in keys if k in norm(s)), "none")
    return find(pred) == find(gold)


def run_one(profile: dict, rfp: dict) -> dict:
    t = trace.start(f"eval:{rfp['id']}")
    opp = extract_opportunity({"url": rfp["url"], "raw_content": rfp["text"]})
    opp["days_left"] = None  # judge fit on substance; labels were made without the clock
    fit = score_fit(profile, opp)
    elig = eligibility.check(profile, {**opp, "due_date": None})
    summary = t.summary()
    labels = rfp["labels"]
    predicted_eligible = elig["verdict"] != "no_go"
    return {
        "id": rfp["id"],
        "checks": {
            "set_aside": set_aside_match(opp.get("set_aside"), labels.get("set_aside")),
            "naics": norm(labels.get("naics")) in [norm(n) for n in opp.get("naics") or []],
            "due_date": (opp.get("due_date") or "")[:10] == (labels.get("due_date") or ""),
            "eligible": predicted_eligible == labels["eligible"],
            "fit": fit["band"] == labels["fit"],
        },
        "pred": {"set_aside": opp.get("set_aside"), "naics": opp.get("naics"), "due_date": opp.get("due_date"),
                 "eligible": predicted_eligible, "fit": fit["band"], "score": fit["score"]},
        "cost": summary["savings"]["actual_usd"],
        "latency_s": summary["duration_ms"] / 1000,
        "tokens": summary["prompt_tokens"] + summary["completion_tokens"],
    }


def run_mode(mode: str, rfps: list[dict], profile: dict) -> list[dict]:
    token = router.set_mode(mode)
    try:
        out = []
        for rfp in rfps:
            start = time.time()
            try:
                out.append(run_one(profile, rfp))
            except Exception as exc:
                out.append({"id": rfp["id"], "error": str(exc), "checks": {}, "cost": 0, "latency_s": time.time() - start})
            print(f"[{mode}] {rfp['id']}: {out[-1].get('checks') or out[-1].get('error')}", flush=True)
        return out
    finally:
        router.reset_mode(token)


def aggregate(rows: list[dict]) -> dict:
    fields = ["set_aside", "naics", "due_date", "eligible", "fit"]
    acc = {}
    for f in fields:
        vals = [r["checks"][f] for r in rows if f in r["checks"]]
        acc[f] = round(100 * sum(vals) / len(vals), 1) if vals else None
    ok = [r for r in rows if "error" not in r]
    return {
        "n": len(rows),
        "errors": len(rows) - len(ok),
        "accuracy": acc,
        "overall": round(sum(v for v in acc.values() if v is not None) / max(1, sum(v is not None for v in acc.values())), 1),
        "cost_usd": round(sum(r["cost"] for r in rows), 4),
        "avg_latency_s": round(sum(r["latency_s"] for r in ok) / max(1, len(ok)), 1),
    }


def to_markdown(results: dict) -> str:
    modes = list(results)
    lines = ["| Metric | " + " | ".join(m.replace("_", "-") for m in modes) + " |",
             "|---|" + "---|" * len(modes)]
    labels = {"set_aside": "Set-aside extraction", "naics": "NAICS extraction", "due_date": "Due date extraction",
              "eligible": "Eligibility (go / no-go)", "fit": "Fit band"}
    for key, label in labels.items():
        lines.append(f"| {label} | " + " | ".join(f"{results[m]['agg']['accuracy'][key]}%" for m in modes) + " |")
    lines.append("| **Overall accuracy** | " + " | ".join(f"**{results[m]['agg']['overall']}%**" for m in modes) + " |")
    lines.append("| Total cost (USD) | " + " | ".join(f"${results[m]['agg']['cost_usd']}" for m in modes) + " |")
    lines.append("| Avg latency / RFP | " + " | ".join(f"{results[m]['agg']['avg_latency_s']}s" for m in modes) + " |")
    if "routed" in results and "ultra_only" in results:
        a, b = results["routed"]["agg"]["cost_usd"], results["ultra_only"]["agg"]["cost_usd"]
        if b:
            lines.append(f"\nRouting cost **{round(100 * (1 - a / b), 1)}% less** than Ultra-only on "
                         f"{results['routed']['agg']['n']} real solicitations.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["routed", "ultra_only", "both"], default="both")
    args = parser.parse_args()
    db.init()
    seed.ensure_seeded()
    profile = db.get_profile(seed.DEMO_ID)
    rfps = load_rfps()
    if not rfps:
        sys.exit("No RFPs in evals/rfps/. Run evals/collect.py first.")
    modes = ["routed", "ultra_only"] if args.mode == "both" else [args.mode]
    results = {}
    for mode in modes:
        rows = run_mode(mode, rfps, profile)
        results[mode] = {"rows": rows, "agg": aggregate(rows)}
    (HERE / "results.json").write_text(json.dumps(results, indent=1))
    md = to_markdown(results)
    (HERE / "results.md").write_text(md + "\n")
    print("\n" + md)


if __name__ == "__main__":
    main()
