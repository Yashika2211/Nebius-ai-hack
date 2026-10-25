"""Grounding: split sources into citable spans and verify that model claims are supported.

Models see sources as `[rfp:12] text...` lines and must cite span IDs plus a short verbatim
quote. `verify_claims` rejects citations that don't exist or whose quote isn't in the span,
so the UI only shows claims that link to real source text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\"'•\-])")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "by", "is", "are",
    "be", "shall", "will", "must", "that", "this", "as", "at", "from", "it", "its", "all", "any",
}


@dataclass
class Span:
    id: str
    text: str
    source: str
    url: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "source": self.source, "url": self.url}


def make_spans(prefix: str, text: str, url: str = "", max_chars: int = 360) -> list[Span]:
    """Split text into spans of whole sentences, each at most ~max_chars long."""
    spans: list[Span] = []
    buf = ""
    for para in re.split(r"\n\s*\n|\n(?=\s*[-•*\d]+[.)]?\s)", text or ""):
        para = " ".join(para.split())
        if not para:
            continue
        for sent in _SENTENCE.split(para):
            if buf and len(buf) + len(sent) + 1 > max_chars:
                spans.append(Span(f"{prefix}:{len(spans) + 1}", buf, prefix, url))
                buf = ""
            buf = f"{buf} {sent}".strip()
        if buf:
            spans.append(Span(f"{prefix}:{len(spans) + 1}", buf, prefix, url))
            buf = ""
    return spans


def render(spans: list[Span], limit_chars: int = 24000) -> str:
    """Format spans for a prompt, truncating to keep within context budget."""
    lines, total = [], 0
    for s in spans:
        line = f"[{s.id}] {s.text}"
        if total + len(line) > limit_chars:
            lines.append("[...truncated...]")
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def overlap(quote: str, span_text: str) -> float:
    """Fraction of the quote's content words that appear in the span (0..1)."""
    q = _tokens(quote)
    if not q:
        return 0.0
    s = set(_tokens(span_text))
    return sum(1 for w in q if w in s) / len(q)


def supports(quote: str, span_text: str, threshold: float = 0.7) -> bool:
    if not quote:
        return False
    norm = lambda t: " ".join(t.lower().split())
    if norm(quote) in norm(span_text):
        return True
    return overlap(quote, span_text) >= threshold


def verify_claims(claims: list[dict], spans: list[Span], threshold: float = 0.7) -> list[dict]:
    """Annotate each claim with `grounded` and resolved `evidence`.

    A claim is grounded when at least one cited span exists and contains its quote
    (or, without a quote, shares most of the claim's content words).
    """
    index = {s.id: s for s in spans}
    out = []
    for claim in claims:
        cites = claim.get("citations") or claim.get("cites") or []
        if isinstance(cites, str):
            cites = [cites]
        cites = [c.strip("[] ") for c in cites]
        quote = (claim.get("quote") or "").strip()
        text = claim.get("text") or claim.get("claim") or ""
        evidence = []
        for cid in cites:
            span = index.get(cid)
            if not span:
                continue
            ok = supports(quote, span.text, threshold) if quote else overlap(text, span.text) >= 0.5
            if ok:
                evidence.append(span.as_dict())
        out.append({**claim, "citations": cites, "grounded": bool(evidence), "evidence": evidence})
    return out


def grounding_rate(claims: list[dict]) -> float:
    if not claims:
        return 1.0
    return sum(1 for c in claims if c.get("grounded")) / len(claims)
