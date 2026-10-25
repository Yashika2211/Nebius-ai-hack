"""Discovery agent: find live solicitations and rank them with a transparent fit score."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .. import grounding, llm, tavily_client, trace
from ..grounding import Span
from ..scoring import FACTORS, combine

PROCUREMENT_DOMAINS = [
    "sam.gov",
    "bidnetdirect.com",
    "caleprocure.ca.gov",
    "esbd.cpa.state.tx.us",
    "txsmartbuy.gov",
    "bidbuy.illinois.gov",
    "nyc.gov",
    "emma.maryland.gov",
    "vendor.myfloridamarketplace.com",
    "procurement.opengov.com",
    "bonfirehub.com",
    "demandstar.com",
    "publicpurchase.com",
]

QUERY_SYSTEM = """You write web search queries that find OPEN government solicitations
(RFP, RFQ, IFB, sources sought) a specific small business could bid on.
Mix federal (SAM.gov) and state/city portals. Use the company's real service terms and
NAICS codes. Return JSON: {"queries": [str, ...]} with 4 to 6 queries."""

TRIAGE_SYSTEM = """You triage search results for a government-contracting assistant.
For each result decide if it is (a) an actual solicitation or opportunity page (not a news
article, award notice, or vendor ad) and (b) plausibly relevant to the company.
Return JSON: {"results": [{"i": int, "relevant": bool, "confidence": 0.0-1.0, "why": str}]}"""

EXTRACT_SYSTEM = """Extract solicitation facts from the page spans. Use null when a field
is not stated. Do not guess dates. Return JSON:
{"title": str, "agency": str | null, "solicitation_number": str | null,
 "type": "RFP|RFQ|IFB|Sources Sought|Other", "due_date": "YYYY-MM-DD" | null,
 "set_aside": str | null, "naics": [str], "place_of_performance": str | null,
 "estimated_value": str | null, "summary": str (2 sentences),
 "is_open_solicitation": bool}"""

FIT_SYSTEM = """You score how well a small business fits a government solicitation.
Score each factor 0-10 and justify it in one sentence. Cite span IDs from the RFP (rfp:N)
and the company profile (profile:N) with a short verbatim quote from one cited span.
Be strict: a capability match must be specific, not generic.

Factors: """ + ", ".join(f"{k} ({v['label']})" for k, v in FACTORS.items()) + """

Return JSON:
{"factors": {"<factor>": {"score": 0-10, "reason": str, "citations": [ids], "quote": str}},
 "headline": str (one sentence a business owner would understand),
 "dealbreakers": [str]}"""

TRIAGE_ESCALATE_BELOW = 0.6


def profile_spans(profile: dict) -> list[Span]:
    """Compact, citable view of the profile for fit scoring."""
    lines = [f"Company: {profile.get('name')}. {profile.get('summary', '')}"]
    for n in profile.get("naics", []):
        lines.append(f"NAICS {n.get('code')} {n.get('title', '')}")
    for c in profile.get("certifications", []):
        lines.append(f"Certification: {c.get('name')} {c.get('detail', '')}")
    for c in profile.get("capabilities", []):
        lines.append(f"Capability: {c.get('text')}")
    for p in profile.get("past_performance", []):
        lines.append(f"Past performance for {p.get('client')}: {p.get('text')} {p.get('value') or ''}")
    for k in ("clearances", "bonding"):
        for c in profile.get(k, []):
            lines.append(f"{k.title()}: {c.get('text')}")
    if profile.get("locations"):
        lines.append("Locations: " + ", ".join(profile["locations"]))
    return [Span(f"profile:{i}", line.strip(), "profile") for i, line in enumerate(lines, start=1)]


def make_queries(profile: dict) -> list[str]:
    summary = {
        "name": profile.get("name"),
        "summary": profile.get("summary"),
        "naics": [n.get("code") for n in profile.get("naics", [])],
        "certifications": [c.get("name") for c in profile.get("certifications", [])],
        "keywords": profile.get("keywords", [])[:12],
        "locations": profile.get("locations", []),
    }
    data = llm.chat_json("discover.queries", QUERY_SYSTEM, json.dumps(summary), max_tokens=600)
    queries = [q for q in data.get("queries", []) if isinstance(q, str)][:6]
    return queries or [f"{' '.join(summary['keywords'][:3])} RFP solicitation"]


def triage(profile: dict, hits: list[dict]) -> list[dict]:
    """Nano filters hits in one batch; low-confidence calls are re-checked on a bigger tier."""
    if not hits:
        return []
    listing = "\n".join(
        f"{i}. {h.get('title', '')} | {h.get('url', '')} | {(h.get('content') or '')[:300]}"
        for i, h in enumerate(hits)
    )
    company = f"Company: {profile.get('name')} — {profile.get('summary', '')}"
    user = f"{company}\n\nRESULTS:\n{listing}"
    verdicts = {v.get("i"): v for v in llm.chat_json("discover.triage", TRIAGE_SYSTEM, user, max_tokens=1500).get("results", [])}

    unsure = [i for i, v in verdicts.items() if v.get("confidence", 0) < TRIAGE_ESCALATE_BELOW]
    if unsure:
        sub = "\n".join(listing.splitlines()[i] for i in unsure if isinstance(i, int) and i < len(hits))
        rechecked = llm.chat_json("discover.triage", TRIAGE_SYSTEM, f"{company}\n\nRESULTS:\n{sub}",
                                  max_tokens=800, escalate=1).get("results", [])
        for v in rechecked:
            if v.get("i") in verdicts:
                verdicts[v["i"]] = {**v, "escalated": True}

    kept = []
    for i, hit in enumerate(hits):
        v = verdicts.get(i, {})
        if v.get("relevant"):
            kept.append({**hit, "triage": v})
    trace.emit({"kind": "check", "name": "triage",
                "detail": f"{len(kept)}/{len(hits)} results kept, {len(unsure)} escalated"})
    return kept


def extract_opportunity(page: dict) -> dict:
    text = page.get("raw_content") or page.get("content") or ""
    spans = grounding.make_spans("rfp", text[:30000], url=page.get("url", ""))
    facts = llm.chat_json("discover.extract", EXTRACT_SYSTEM, grounding.render(spans, 12000), max_tokens=800)
    return {
        **facts,
        "url": page.get("url"),
        "source_text": text[:60000],
        "days_left": days_until(facts.get("due_date")),
    }


def days_until(due: str | None) -> int | None:
    if not due:
        return None
    try:
        return (date.fromisoformat(due[:10]) - date.today()).days
    except ValueError:
        return None


def score_fit(profile: dict, opp: dict) -> dict:
    rfp = grounding.make_spans("rfp", opp.get("source_text", "")[:30000], url=opp.get("url", ""))
    prof = profile_spans(profile)
    user = (
        f"TODAY: {date.today().isoformat()}\n\nCOMPANY PROFILE:\n{grounding.render(prof, 6000)}\n\n"
        f"SOLICITATION ({opp.get('title')}):\n{grounding.render(rfp, 14000)}"
    )
    raw = llm.chat_json("discover.fit", FIT_SYSTEM, user, max_tokens=2000)
    factors = {}
    for key in FACTORS:
        f = (raw.get("factors") or {}).get(key) or {"score": 0, "reason": "Not assessed"}
        [checked] = grounding.verify_claims([{"text": f.get("reason", ""), **f}], rfp + prof)
        factors[key] = checked
    fit = combine(factors, opp.get("days_left"))
    return {**fit, "headline": raw.get("headline", ""), "dealbreakers": raw.get("dealbreakers") or []}


def discover(profile: dict, max_opps: int = 5, extra_query: str = "") -> list[dict]:
    trace.step("Discovery", "Planning searches from your profile")
    queries = make_queries(profile)
    if extra_query:
        queries.insert(0, extra_query)

    trace.step("Search", f"{len(queries)} queries across SAM.gov and state/city portals")
    hits, seen = [], set()
    for q in queries:
        for h in tavily_client.search(q, include_domains=PROCUREMENT_DOMAINS, max_results=8):
            if h.get("url") and h["url"] not in seen:
                seen.add(h["url"])
                hits.append(h)

    trace.step("Triage", f"Filtering {len(hits)} results")
    relevant = triage(profile, hits)
    relevant.sort(key=lambda h: (h["triage"].get("confidence", 0), h.get("score", 0)), reverse=True)
    top = relevant[: max_opps + 2]
    if not top:
        return []

    trace.step("Read solicitations", f"Extracting full text of {len(top)} pages")
    pages = tavily_client.extract([h["url"] for h in top])
    with ThreadPoolExecutor(max_workers=4) as pool:
        opps = list(pool.map(_with_trace(extract_opportunity), pages))
    opps = [o for o in opps if o.get("is_open_solicitation", True)][:max_opps]

    trace.step("Fit scoring", f"Scoring {len(opps)} opportunities")
    with ThreadPoolExecutor(max_workers=4) as pool:
        fits = list(pool.map(_with_trace(lambda o: score_fit(profile, o)), opps))
    for opp, fit in zip(opps, fits):
        opp["fit"] = fit
    opps.sort(key=lambda o: o["fit"]["score"], reverse=True)
    return opps


def _with_trace(fn):
    """Propagate the current trace into pool threads (ThreadPoolExecutor doesn't copy context)."""
    import contextvars

    ctx = contextvars.copy_context()

    def run(arg):
        return ctx.copy().run(fn, arg)

    return run
