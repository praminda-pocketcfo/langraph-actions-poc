"""Shared evaluation state types."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


Level = Literal["missing", "partial", "met"]
Recommendation = Literal["pass", "borderline", "fail"]
EvalStatus = Literal["pending", "running", "awaiting_panel", "error"]


class Criterion(TypedDict, total=False):
    id: str
    area: str
    mode: str
    max_points: int
    description: str


class Rubric(TypedDict, total=False):
    project_id: str
    pass_threshold: int
    borderline_threshold: int
    max_points: int
    criteria: list[Criterion]


class TestSummary(TypedDict, total=False):
    passed: int
    failed: int
    errors: int
    total: int
    details: list[dict[str, Any]]


class CriterionFinding(TypedDict, total=False):
    id: str
    area: str
    level: Level
    evidence: str
    points: int
    max: int


class ScoreResult(TypedDict, total=False):
    total: int
    max: int
    recommendation: Recommendation
    criteria: list[CriterionFinding]


class EvaluationState(TypedDict, total=False):
    evaluation_id: str
    submission_repo: str
    pr_number: int
    head_sha: str
    project_id: str
    run_url: str
    submission_files: dict[str, str]
    junit: TestSummary
    rubric: Rubric
    findings: Annotated[list[CriterionFinding], lambda a, b: (a or []) + (b or [])]
    verified: list[CriterionFinding]
    score: ScoreResult
    feedback_markdown: str
    status: EvalStatus
    error: str
    messages: Annotated[list, add_messages]
