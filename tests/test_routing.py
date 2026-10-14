from evaluator.scoring import group_criteria_by_area


def test_group_criteria_skips_tests_mode():
    criteria = [
        {"id": "unit_tests", "area": "tests", "mode": "tests", "max_points": 40},
        {"id": "handles_edge_cases", "area": "correctness", "mode": "agent", "max_points": 30},
        {"id": "clear_structure", "area": "structure", "mode": "agent", "max_points": 30},
    ]
    groups = group_criteria_by_area(criteria)
    assert set(groups) == {"correctness", "structure"}
    assert [c["id"] for c in groups["correctness"]] == ["handles_edge_cases"]
    assert [c["id"] for c in groups["structure"]] == ["clear_structure"]
