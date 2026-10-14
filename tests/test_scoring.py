from evaluator.scoring import compute_score, level_from_tests, points_for_level, recommendation_for, score_tests_criterion


def test_points_for_level():
    assert points_for_level(40, "missing") == 0
    assert points_for_level(40, "partial") == 20
    assert points_for_level(40, "met") == 40


def test_level_from_tests():
    assert level_from_tests({"passed": 0, "total": 0}) == "missing"
    assert level_from_tests({"passed": 0, "total": 4}) == "missing"
    assert level_from_tests({"passed": 2, "total": 4}) == "partial"
    assert level_from_tests({"passed": 4, "total": 4}) == "met"


def test_score_tests_criterion():
    finding = score_tests_criterion(
        {"id": "unit_tests", "area": "tests", "max_points": 40},
        {"passed": 3, "total": 6, "failed": 3, "errors": 0},
    )
    assert finding["level"] == "partial"
    assert finding["points"] == 20


def test_recommendation_thresholds():
    rubric = {"pass_threshold": 70, "borderline_threshold": 50, "max_points": 100}
    assert recommendation_for(80, rubric) == "pass"
    assert recommendation_for(55, rubric) == "borderline"
    assert recommendation_for(10, rubric) == "fail"


def test_compute_score():
    rubric = {
        "pass_threshold": 70,
        "borderline_threshold": 50,
        "max_points": 100,
        "criteria": [],
    }
    verified = [
        {"id": "a", "area": "tests", "level": "met", "points": 40, "max": 40, "evidence": ""},
        {"id": "b", "area": "correctness", "level": "partial", "points": 15, "max": 30, "evidence": ""},
        {"id": "c", "area": "structure", "level": "met", "points": 30, "max": 30, "evidence": ""},
    ]
    score = compute_score(verified, rubric)
    assert score["total"] == 85
    assert score["recommendation"] == "pass"
