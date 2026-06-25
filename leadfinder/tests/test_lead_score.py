import pytest
from leadfinder.lead_score import calculate_lead_score


def test_perfect_site_scores_zero():
    assert calculate_lead_score(100, 100, 100, 1) == 0.0


def test_terrible_site_scores_above_seventy():
    assert calculate_lead_score(10, 15, 20, 0) > 70


def test_worst_case_scores_exactly_one_hundred():
    assert calculate_lead_score(0, 0, 0, 0) == 100.0


def test_mobile_friendly_adds_twenty_five_points():
    score_without = calculate_lead_score(50, 50, 50, 0)
    score_with = calculate_lead_score(50, 50, 50, 1)
    assert score_without == pytest.approx(score_with + 25)


def test_score_capped_at_one_hundred():
    assert calculate_lead_score(-100, -100, -100, -100) == 100.0
