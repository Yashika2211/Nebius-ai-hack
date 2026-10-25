"""Onboarding agent: crawl a company site and build a grounded company profile."""
from __future__ import annotations

from .. import grounding, llm, tavily_client, trace
from ..grounding import Span

CRAWL_INSTRUCTIONS = (
    "Find pages about the company's services, capabilities, past performance, clients, "
    "certifications (8(a), HUBZone, WOSB, SDVOSB), NAICS codes, and contact/location."
)

SYSTEM = """You build company profiles for US government contracting.
You are given numbered source spans from the company's website and the owner's own notes.
Extract ONLY facts stated in the spans. Every item must cite span IDs and include a short
verbatim quote (under 20 words) copied from one cited span. Never invent NAICS codes,
certifications, clients, or dollar values. If something is not stated, leave it out.

Return JSON:
{
  "name": str,
  "summary": str (2 sentences, plain language),
  "locations": [str],
  "employee_count": str | null,
  "naics": [{"code": "6 digits", "title": str, "citations": [span ids], "quote": str}],
  "certifications": [{"name": "8(a)|HUBZone|WOSB|EDWOSB|SDVOSB|VOSB|SDB|DBE|MBE|WBE|other", "detail": str, "citations": [...], "quote": str}],
  "capabilities": [{"text": str, "citations": [...], "quote": str}],
  "past_performance": [{"client": str, "text": str, "value": str | null, "citations": [...], "quote": str}],
  "clearances": [{"text": str, "citations": [...], "quote": str}],
  "bonding": [{"text": str, "citations": [...], "quote": str}],
  "keywords": [str] (8-15 search terms a contracting officer would use for this work)
}"""

GROUNDED_LISTS = ["naics", "certifications", "capabilities", "past_performance", "clearances", "bonding"]


def gather_site(website: str) -> list[dict]:
    """Crawl the site; fall back to extracting just the homepage."""
    pages: list[dict] = []
    try:
        pages = tavily_client.crawl(website, instructions=CRAWL_INSTRUCTIONS)
    except Exception as exc:
        trace.emit({"kind": "note", "detail": f"Crawl failed ({exc}); extracting homepage only"})
    if not pages:
        pages = tavily_client.extract([website])
    return pages


def build_spans(pages: list[dict], notes: str) -> list[Span]:
    spans: list[Span] = []
    for i, page in enumerate(pages[:12], start=1):
        text = page.get("raw_content") or page.get("content") or ""
        spans += grounding.make_spans(f"site{i}", text[:8000], url=page.get("url", ""))
    if notes.strip():
        spans += grounding.make_spans("notes", notes, url="")
    return spans


def build_profile(website: str, notes: str = "", name: str = "") -> dict:
    trace.step("Onboarding", f"Reading {website or 'your notes'}")
    pages = gather_site(website) if website else []
    spans = build_spans(pages, notes)
    if not spans:
        raise ValueError("No content found on the website and no notes provided.")

    trace.step("Profile extraction", f"{len(spans)} source spans from {len(pages)} page(s)")
    hint = f"The company name is {name}.\n" if name else ""
    raw = llm.chat_json(
        "profile.extract",
        SYSTEM,
        f"{hint}SOURCE SPANS:\n{grounding.render(spans)}",
        max_tokens=3000,
    )
    return finalize(raw, spans, website, name)


def finalize(raw: dict, spans: list[Span], website: str, name: str = "") -> dict:
    """Verify every grounded item and drop the ones whose citation doesn't hold up."""
    profile = {
        "name": raw.get("name") or name or website,
        "website": website,
        "summary": raw.get("summary", ""),
        "locations": raw.get("locations") or [],
        "employee_count": raw.get("employee_count"),
        "keywords": raw.get("keywords") or [],
        "spans": [s.as_dict() for s in spans],
        "dropped": [],
    }
    for key in GROUNDED_LISTS:
        checked = grounding.verify_claims(raw.get(key) or [], spans)
        profile[key] = [c for c in checked if c["grounded"]]
        profile["dropped"] += [{"field": key, **c} for c in checked if not c["grounded"]]
    kept = sum(len(profile[k]) for k in GROUNDED_LISTS)
    trace.emit({
        "kind": "check",
        "name": "grounding",
        "detail": f"{kept} facts verified against source, {len(profile['dropped'])} unsupported dropped",
    })
    return profile
