from app.agents.draft import check_statement, shall_statements
from app.agents.eligibility import set_aside_check
from app.grounding import make_spans

PROFILE = {"certifications": [{"name": "WOSB"}]}


def test_set_aside_eligible_with_matching_cert():
    assert set_aside_check("Women-Owned Small Business (WOSB)", PROFILE)["eligible"] is True


def test_set_aside_ineligible_without_cert():
    assert set_aside_check("8(a) Set-Aside", PROFILE)["eligible"] is False
    assert set_aside_check("SDVOSB", PROFILE)["eligible"] is False


def test_small_business_set_aside_is_undetermined():
    assert set_aside_check("Total Small Business Set-Aside", PROFILE)["eligible"] is None


def test_no_set_aside():
    assert set_aside_check(None, PROFILE) is None
    assert set_aside_check("Full and open competition", PROFILE) is None


def test_shall_statements_prepass():
    spans = make_spans("rfp", "The contractor shall clean floors.\n\nBackground on the agency.\n\nOfferors must submit a quote.")
    assert [s.text for s in shall_statements(spans)] == ["The contractor shall clean floors.", "Offerors must submit a quote."]


def test_check_statement_flags_uncited_and_fake_citations():
    spans = make_spans("profile", "Ridgeline cleans six clinic sites for Bexar County.")
    text = (
        "Ridgeline cleans six clinic sites for Bexar County [profile:1]. "
        "We have cleaned the Pentagon for twenty years without issue. "
        "Ridgeline cleans six clinic sites for Bexar County [profile:9]. "
        "[OWNER TO CONFIRM: bonding capacity for this contract value]."
    )
    out = check_statement(text, spans)
    assert [s["grounded"] for s in out["sentences"]] == [True, False, False, True]
    assert out["sentences"][3]["needs_owner"]
