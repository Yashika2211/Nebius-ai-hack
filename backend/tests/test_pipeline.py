"""End-to-end golden path with Token Factory and Tavily faked at the network boundary."""
import json

import pytest
from fastapi.testclient import TestClient

from app import llm, tavily_client
from app.config import settings

RFP_TEXT = """Solicitation 36C25726Q0099: Custodial Services, San Antonio VA Outpatient Clinic.

This is a 100% Women-Owned Small Business (WOSB) set-aside under NAICS 561720.

The contractor shall provide daily custodial services for 45,000 square feet of clinic space.

The contractor shall use EPA Safer Choice certified cleaning products.

Offerors must provide three references for similar healthcare cleaning contracts.

Quotes are due December 15, 2026."""


def fake_call(model, messages, json_mode, max_tokens, temperature, on_token):
    system = messages[0]["content"]
    usage = {"prompt_tokens": 1200, "completion_tokens": 300}
    if "write web search queries" in system:
        out = {"queries": ["janitorial services RFP San Antonio"]}
    elif "triage search results" in system:
        out = {"results": [{"i": 0, "relevant": True, "confidence": 0.9, "why": "custodial RFP"},
                           {"i": 1, "relevant": False, "confidence": 0.4, "why": "news"}]}
    elif "Extract solicitation facts" in system:
        out = {"title": "Custodial Services, San Antonio VA Outpatient Clinic", "agency": "VA",
               "solicitation_number": "36C25726Q0099", "type": "RFQ", "due_date": "2026-12-15",
               "set_aside": "Women-Owned Small Business (WOSB)", "naics": ["561720"],
               "place_of_performance": "San Antonio, TX", "estimated_value": None,
               "summary": "Daily custodial services.", "is_open_solicitation": True}
    elif "score how well" in system:
        out = {"factors": {k: {"score": 9, "reason": "Janitorial Services NAICS 561720 matches",
                               "citations": ["profile:2"], "quote": "NAICS 561720 Janitorial Services"}
                           for k in ["naics_match", "capability_match", "set_aside_eligibility",
                                     "past_performance", "location_feasibility", "deadline_feasibility"]},
               "headline": "Strong fit", "dealbreakers": []}
    elif "extract eligibility" in system:
        out = {"requirements": [{"id": "R1", "category": "experience", "text": "Three healthcare references",
                                 "mandatory": True, "citations": ["rfp:5"],
                                 "quote": "three references for similar healthcare cleaning contracts"}]}
    elif "decide whether" in system:
        out = {"decisions": [{"id": "R1", "status": "met", "dealbreaker": False, "explanation": "Clinic work",
                              "action": "Attach references", "citations": ["profile:12"],
                              "quote": "Bexar County Health Clinic network"}],
               "verdict": "go", "verdict_reason": "Eligible."}
    elif "compliance reviewer" in system:
        out = {"issues": [], "ready_to_submit": True, "summary": "Looks good"}
    elif "compliance matrix" in system:
        out = {"rows": [{"req_id": "rfp:3", "requirement": "Daily custodial", "section": "2.1",
                         "response": "We clean clinics daily", "gap": False, "citations": ["profile:7"],
                         "quote": "Janitorial and custodial services"}]}
    else:  # capability statement (streamed)
        text = "## Executive Summary\nRidgeline provides janitorial and custodial services, including floor care [profile:7]."
        if on_token:
            for word in text.split(" "):
                on_token(word + " ")
        return text, usage
    return json.dumps(out), usage


def fake_post(endpoint, payload, summary, timeout=60):
    if endpoint == "search":
        return {"results": [{"title": "Custodial Services VA clinic", "url": "https://sam.gov/opp/1", "content": "RFQ"},
                            {"title": "Local news", "url": "https://sam.gov/news", "content": "news"}]}
    if endpoint == "extract":
        return {"results": [{"url": u, "raw_content": RFP_TEXT} for u in payload["urls"]]}
    return {"results": []}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "nebius_api_key", "test")
    monkeypatch.setattr(settings, "tavily_api_key", "test")
    monkeypatch.setattr(settings, "demo_mode", "live")
    monkeypatch.setattr(llm, "_call", fake_call)
    monkeypatch.setattr(tavily_client, "_post", fake_post)
    from app import models
    monkeypatch.setattr(models, "_resolved", {"nano": "n", "super": "s", "ultra": "u"})
    from app.main import app
    with TestClient(app) as c:
        yield c


def sse(resp):
    return [json.loads(line[5:]) for line in resp.text.splitlines() if line.startswith("data:")]


def test_golden_path(client):
    pid = "demo-ridgeline"
    events = sse(client.post(f"/api/profiles/{pid}/discover", json={}))
    result = next(e for e in events if e["type"] == "result")["result"]
    assert len(result) == 1
    opp = result[0]
    assert opp["fit"]["score"] >= 75
    assert all(f["grounded"] for f in opp["fit"]["factors"] if f["key"] != "deadline_feasibility")
    tiers = {e["event"]["tier"] for e in events if e["type"] == "trace" and e["event"]["kind"] == "llm"}
    assert {"nano", "ultra"} <= tiers
    done = next(e for e in events if e["type"] == "done")["summary"]
    assert done["savings"]["saved_pct"] > 0

    events = sse(client.post(f"/api/profiles/{pid}/opportunities/{opp['id']}/eligibility"))
    elig = next(e for e in events if e["type"] == "result")["result"]
    assert elig["verdict"] == "go"
    assert elig["items"][0]["status"] == "met"

    events = sse(client.post(f"/api/profiles/{pid}/opportunities/{opp['id']}/draft"))
    assert any(e["type"] == "token" for e in events)
    draft = next(e for e in events if e["type"] == "result")["result"]
    assert draft["matrix"][0]["grounded"]
    assert draft["statement_check"]["grounding_rate"] == 1.0
    assert draft["review"]["ready_to_submit"] is True

    detail = client.get(f"/api/opportunities/{opp['id']}").json()
    assert detail["eligibility"]["verdict"] == "go" and detail["draft"]
    assert client.get("/api/stats").json()["saved_pct"] > 0


def test_replay_mode_serves_cache_without_keys(client, monkeypatch):
    pid = "demo-ridgeline"
    sse(client.post(f"/api/profiles/{pid}/discover", json={}))
    monkeypatch.setattr(settings, "nebius_api_key", "")
    monkeypatch.setattr(settings, "demo_mode", "auto")
    monkeypatch.setattr(llm, "_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no live call")))
    events = sse(client.post(f"/api/profiles/{pid}/discover", json={}))
    assert any(e["type"] == "result" for e in events)
    llm_events = [e["event"] for e in events if e["type"] == "trace" and e["event"]["kind"] == "llm"]
    assert llm_events and all(e["cached"] for e in llm_events)


def test_watch_run_all_requires_token(client, monkeypatch):
    assert client.post("/api/watch/run-all").status_code == 401
    monkeypatch.setattr(settings, "watch_token", "secret")
    assert client.post("/api/watch/run-all", headers={"Authorization": "Bearer nope"}).status_code == 401
    resp = client.post("/api/watch/run-all", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    assert resp.json()["demo-ridgeline"] == 1
    runs = client.get("/api/profiles/demo-ridgeline/watch").json()
    assert runs[0]["new_count"] == 1
