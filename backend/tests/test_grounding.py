from app.grounding import grounding_rate, make_spans, overlap, render, supports, verify_claims

RFP = """The contractor shall provide daily custodial services at three clinic buildings.

This acquisition is a 100% Women-Owned Small Business (WOSB) set-aside under NAICS 561720.
Offerors must hold general liability insurance of at least $1,000,000. Responses are due November 14, 2026."""


def test_make_spans_ids_and_text():
    spans = make_spans("rfp", RFP, url="https://sam.gov/x")
    assert spans[0].id == "rfp:1"
    assert "custodial" in spans[0].text
    assert all(s.url == "https://sam.gov/x" for s in spans)
    assert all(len(s.text) <= 400 for s in spans)


def test_long_paragraph_is_split():
    text = " ".join(f"Sentence number {i} is about cleaning." for i in range(40))
    spans = make_spans("x", text, max_chars=200)
    assert len(spans) > 3
    assert all(len(s.text) <= 240 for s in spans)


def test_render_truncates():
    spans = make_spans("x", " ".join(f"Sentence {i} here." for i in range(500)), max_chars=50)
    assert "[...truncated...]" in render(spans, limit_chars=500)


def test_supports_exact_and_fuzzy():
    span = "This acquisition is a 100% Women-Owned Small Business (WOSB) set-aside under NAICS 561720."
    assert supports("Women-Owned Small Business (WOSB) set-aside", span)
    assert supports("WOSB set aside under NAICS 561720", span)
    assert not supports("requires a Top Secret facility clearance", span)
    assert not supports("", span)


def test_overlap_ignores_stopwords():
    assert overlap("the and of", "anything") == 0.0
    assert overlap("custodial services", "daily custodial services") == 1.0


def test_verify_claims_accepts_supported_and_rejects_fabricated():
    spans = make_spans("rfp", RFP)
    wosb = next(s.id for s in spans if "WOSB" in s.text)
    claims = [
        {"text": "WOSB set-aside", "citations": [wosb], "quote": "Women-Owned Small Business (WOSB) set-aside"},
        {"text": "Needs clearance", "citations": [wosb], "quote": "Top Secret clearance required"},
        {"text": "Bad cite", "citations": ["rfp:99"], "quote": "custodial services"},
        {"text": "No cite", "quote": "custodial services"},
    ]
    out = verify_claims(claims, spans)
    assert [c["grounded"] for c in out] == [True, False, False, False]
    assert out[0]["evidence"][0]["id"] == wosb
    assert grounding_rate(out) == 0.25


def test_verify_claims_normalizes_bracketed_and_string_citations():
    spans = make_spans("rfp", RFP)
    out = verify_claims([{"text": "x", "citations": "[rfp:1]", "quote": "daily custodial services"}], spans)
    assert out[0]["grounded"] and out[0]["citations"] == ["rfp:1"]


def test_grounding_rate_empty_is_one():
    assert grounding_rate([]) == 1.0
