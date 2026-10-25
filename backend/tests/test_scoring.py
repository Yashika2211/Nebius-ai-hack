from app.scoring import FACTORS, combine, deadline_score


def all_factors(score=8, grounded=True):
    return {k: {"score": score, "reason": "r", "grounded": grounded} for k in FACTORS}


def test_weights_sum_to_one():
    assert abs(sum(f["weight"] for f in FACTORS.values()) - 1.0) < 1e-9


def test_perfect_score_is_100():
    assert combine(all_factors(10))["score"] == 100


def test_ungrounded_reasons_count_half():
    assert combine(all_factors(10, grounded=False))["score"] == 50


def test_expired_deadline_zeroes_score():
    out = combine(all_factors(10), days_left=-1)
    assert out["score"] == 0 and out["band"] == "weak"


def test_set_aside_ineligible_caps_score():
    f = all_factors(10)
    f["set_aside_eligibility"]["score"] = 0
    assert combine(f)["score"] <= 20


def test_deadline_score_bands():
    assert deadline_score(None) is None
    assert deadline_score(2) == 3.0
    assert deadline_score(30) == 10.0


def test_bad_scores_are_clamped():
    f = all_factors(8)
    f["naics_match"]["score"] = "n/a"
    f["capability_match"]["score"] = 50
    out = combine(f)
    assert 0 <= out["score"] <= 100
    by_key = {b["key"]: b for b in out["factors"]}
    assert by_key["naics_match"]["score"] == 0 and by_key["capability_match"]["score"] == 10
