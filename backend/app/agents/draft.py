"""Drafting agent: compliance matrix + grounded capability statement + final review."""
from __future__ import annotations

import re
from typing import Callable

from .. import grounding, llm, trace
from ..grounding import Span
from .discover import profile_spans

SHALL = re.compile(r"\b(shall|must|is required to|are required to|will be required to)\b", re.IGNORECASE)

MATRIX_SYSTEM = """You build a compliance matrix for a government proposal.
You get numbered "shall/must" statements from the solicitation and the company profile spans.
For EACH statement, say which proposal section addresses it and how, citing profile spans
(profile:N) as evidence when the company can show it. If the profile has no evidence, set
"gap": true and say what the owner must supply. Never claim capabilities not in the profile.

Return JSON: {"rows": [{"req_id": "rfp:N", "requirement": str (short paraphrase),
"section": str (e.g. "2.1 Technical Approach"), "response": str (one sentence),
"gap": bool, "citations": [profile ids], "quote": str}]}"""

STATEMENT_SYSTEM = """You write a first-draft capability statement / proposal cover narrative
for a small business responding to a specific solicitation.
Rules:
- Every factual sentence about the company ends with citations like [profile:3].
- Every sentence about the solicitation's needs ends with citations like [rfp:12].
- Use only facts in the spans. Where evidence is missing write "[OWNER TO CONFIRM: ...]".
- Sections (markdown ## headings): Executive Summary, Understanding of the Requirement,
  Technical Approach, Relevant Past Performance, Certifications & Eligibility, Why Us.
- Plain, confident language. 450-650 words."""

REVIEW_SYSTEM = """You are a federal proposal compliance reviewer. Check the draft against
the compliance matrix and the sources. Flag: unsupported claims, missing mandatory
requirements, wrong set-aside or certification claims, and risky promises.
Return JSON: {"issues": [{"severity": "high|medium|low", "issue": str, "fix": str}],
"ready_to_submit": bool, "summary": str (one sentence)}"""


def shall_statements(spans: list[Span], limit: int = 40) -> list[Span]:
    """Deterministic pre-pass: spans that contain binding requirement language."""
    return [s for s in spans if SHALL.search(s.text)][:limit]


_CITE = re.compile(r"\[((?:profile|rfp):\d+(?:\s*,\s*(?:profile|rfp):\d+)*)\]")


def check_statement(text: str, spans: list[Span]) -> dict:
    """Split the draft into sentences and verify each citation points at a real span."""
    index = {s.id: s for s in spans}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    results = []
    for sent in sentences:
        if sent.startswith("#") or len(sent) < 25:
            continue
        ids = [i.strip() for m in _CITE.findall(sent) for i in m.split(",")]
        bare = _CITE.sub("", sent)
        confirm = "OWNER TO CONFIRM" in sent
        evidence = [index[i].as_dict() for i in ids if i in index and grounding.overlap(bare, index[i].text) >= 0.2]
        results.append({
            "sentence": sent,
            "citations": ids,
            "grounded": bool(evidence) or confirm,
            "needs_owner": confirm,
            "evidence": evidence,
        })
    cited = [r for r in results if r["citations"] or r["needs_owner"]]
    rate = sum(1 for r in results if r["grounded"]) / len(results) if results else 1.0
    return {"sentences": results, "grounding_rate": round(rate, 3), "cited": len(cited), "total": len(results)}


def draft(profile: dict, opp: dict, on_token: Callable[[str], None] | None = None) -> dict:
    rfp = grounding.make_spans("rfp", opp.get("source_text", "")[:40000], url=opp.get("url", ""))
    prof = profile_spans(profile)
    shalls = shall_statements(rfp)

    trace.step("Compliance matrix", f"Mapping {len(shalls)} binding requirements")
    rows = []
    if shalls:
        raw = llm.chat_json(
            "draft.matrix",
            MATRIX_SYSTEM,
            f"PROFILE:\n{grounding.render(prof, 6000)}\n\nREQUIREMENTS:\n{grounding.render(shalls, 14000)}",
            max_tokens=4000,
        )
        rfp_index = {s.id: s for s in rfp}
        for row in grounding.verify_claims(raw.get("rows", []), prof):
            src = rfp_index.get(str(row.get("req_id", "")).strip("[] "))
            row["source"] = src.as_dict() if src else None
            if not row["grounded"]:
                row["gap"] = True
            rows.append(row)

    trace.step("Draft", "Writing a grounded first draft")
    statement = llm.chat(
        "draft.statement",
        [
            {"role": "system", "content": STATEMENT_SYSTEM},
            {"role": "user", "content": (
                f"SOLICITATION: {opp.get('title')} ({opp.get('agency') or 'agency not stated'})\n\n"
                f"PROFILE SPANS:\n{grounding.render(prof, 6000)}\n\n"
                f"SOLICITATION SPANS:\n{grounding.render(rfp, 12000)}"
            )},
        ],
        max_tokens=1800,
        temperature=0.4,
        on_token=on_token,
    )
    checked = check_statement(statement, rfp + prof)

    trace.step("Final review", "Compliance review of the draft")
    gaps = [r for r in rows if r.get("gap")]
    review = llm.chat_json(
        "draft.review",
        REVIEW_SYSTEM,
        f"DRAFT:\n{statement}\n\nMATRIX GAPS:\n" + "\n".join(f"- {r.get('requirement')}" for r in gaps)
        + f"\n\nUNGROUNDED SENTENCES:\n" + "\n".join(
            f"- {s['sentence']}" for s in checked["sentences"] if not s["grounded"]),
        max_tokens=1200,
    )
    trace.emit({"kind": "check", "name": "grounding",
                "detail": f"{int(checked['grounding_rate'] * 100)}% of draft sentences grounded; "
                          f"{len(gaps)} matrix gaps"})
    return {
        "matrix": rows,
        "statement": statement,
        "statement_check": checked,
        "review": review,
        "counts": {"requirements": len(rows), "gaps": len(gaps)},
    }
