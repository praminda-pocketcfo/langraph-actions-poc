"""Code-only scoring from verified criterion levels."""

from __future__ import annotations

from .state import Criterion, CriterionFinding, Level, Recommendation, Rubric, ScoreResult, TestSummary

LEVEL_FRACTION: dict[Level, float] = {
    "missing": 0.0,
    "partial": 0.5,
    "met": 1.0,
}


def points_for_level(max_points: int, level: Level) -> int:
    return int(round(max_points * LEVEL_FRACTION[level]))


def level_from_tests(junit: TestSummary) -> Level:
    total = int(junit.get("total") or 0)
    passed = int(junit.get("passed") or 0)
    if total <= 0:
        return "missing"
    if passed >= total:
        return "met"
    if passed == 0:
        return "missing"
    return "partial"


def score_tests_criterion(criterion: Criterion, junit: TestSummary) -> CriterionFinding:
    level = level_from_tests(junit)
    max_points = int(criterion.get("max_points") or 0)
    passed = int(junit.get("passed") or 0)
    total = int(junit.get("total") or 0)
    return CriterionFinding(
        id=str(criterion["id"]),
        area=str(criterion.get("area") or "tests"),
        level=level,
        evidence=f"Unit tests: {passed}/{total} passed.",
        points=points_for_level(max_points, level),
        max=max_points,
    )


def recommendation_for(total: int, rubric: Rubric) -> Recommendation:
    pass_at = int(rubric.get("pass_threshold") or 70)
    border_at = int(rubric.get("borderline_threshold") or 50)
    if total >= pass_at:
        return "pass"
    if total >= border_at:
        return "borderline"
    return "fail"


def compute_score(verified: list[CriterionFinding], rubric: Rubric) -> ScoreResult:
    total = sum(int(row.get("points") or 0) for row in verified)
    max_points = int(rubric.get("max_points") or sum(int(c.get("max_points") or 0) for c in rubric.get("criteria") or []))
    return ScoreResult(
        total=total,
        max=max_points,
        recommendation=recommendation_for(total, rubric),
        criteria=list(verified),
    )


def group_criteria_by_area(criteria: list[Criterion]) -> dict[str, list[Criterion]]:
    groups: dict[str, list[Criterion]] = {}
    for criterion in criteria:
        mode = criterion.get("mode") or "agent"
        if mode == "tests":
            continue
        area = str(criterion.get("area") or "general")
        groups.setdefault(area, []).append(criterion)
    return groups
