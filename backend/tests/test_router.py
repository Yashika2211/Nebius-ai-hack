from app import router
from app.router import cost, route, savings


def test_tasks_route_to_expected_tiers():
    assert route("discover.triage")[0] == "nano"
    assert route("draft.statement")[0] == "super"
    assert route("eligibility.decide")[0] == "ultra"


def test_unknown_task_defaults_to_super():
    tier, reason = route("something.new")
    assert tier == "super"
    assert "Default" in reason


def test_escalation_moves_up_and_caps_at_ultra():
    assert route("discover.triage", escalate=1)[0] == "super"
    assert route("discover.triage", escalate=5)[0] == "ultra"
    assert "Escalated" in route("discover.triage", escalate=1)[1]


def test_ultra_only_mode_overrides_routing():
    token = router.set_mode("ultra_only")
    try:
        assert route("discover.triage")[0] == "ultra"
    finally:
        router.reset_mode(token)
    assert route("discover.triage")[0] == "nano"


def test_cost_uses_per_million_prices():
    # 1M in + 1M out on ultra at $1/$3
    assert abs(cost("ultra", 1_000_000, 1_000_000) - 4.0) < 1e-9
    assert cost("nano", 1000, 1000) < cost("super", 1000, 1000) < cost("ultra", 1000, 1000)


def test_savings_compares_against_ultra_baseline():
    events = [
        {"kind": "llm", "tier": "nano", "prompt_tokens": 10_000, "completion_tokens": 1000,
         "cost": cost("nano", 10_000, 1000)},
        {"kind": "llm", "tier": "ultra", "prompt_tokens": 5000, "completion_tokens": 500,
         "cost": cost("ultra", 5000, 500)},
        {"kind": "tool", "tool": "tavily.search"},
    ]
    s = savings(events)
    assert s["calls_by_tier"] == {"nano": 1, "ultra": 1}
    assert s["ultra_only_usd"] > s["actual_usd"]
    assert 0 < s["saved_pct"] < 100


def test_savings_with_no_calls_is_zero():
    assert savings([])["saved_pct"] == 0.0
