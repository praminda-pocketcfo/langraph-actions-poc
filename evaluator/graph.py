"""LangGraph evaluation workflow."""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from .models import get_chat_model
from .scoring import compute_score, group_criteria_by_area, points_for_level, score_tests_criterion
from .state import CriterionFinding, EvaluationState, Level


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _normalize_level(value: Any) -> Level:
    level = str(value or "missing").lower().strip()
    if level in {"missing", "partial", "met"}:
        return level  # type: ignore[return-value]
    return "missing"


def route_node(state: EvaluationState) -> dict[str, Any]:
    """Code router: score test criteria; fan out agent criteria by area."""
    rubric = state.get("rubric") or {}
    criteria = list(rubric.get("criteria") or [])
    findings: list[CriterionFinding] = []
    for criterion in criteria:
        if (criterion.get("mode") or "agent") == "tests":
            findings.append(score_tests_criterion(criterion, state.get("junit") or {}))
    return {"findings": findings, "status": "running"}


def route_to_specialists(state: EvaluationState) -> list[Send] | Literal["verifier"]:
    rubric = state.get("rubric") or {}
    groups = group_criteria_by_area(list(rubric.get("criteria") or []))
    if not groups:
        return "verifier"
    sends: list[Send] = []
    for area, criteria in groups.items():
        sends.append(
            Send(
                "specialist",
                {
                    "area": area,
                    "criteria": criteria,
                    "submission_files": state.get("submission_files") or {},
                    "junit": state.get("junit") or {},
                    "project_id": state.get("project_id"),
                },
            )
        )
    return sends


def make_specialist_node(model: BaseChatModel):
    def specialist(payload: dict[str, Any]) -> dict[str, Any]:
        area = payload.get("area") or "general"
        criteria = payload.get("criteria") or []
        files = payload.get("submission_files") or {}
        file_blob = "\n\n".join(f"### {path}\n```\n{content[:4000]}\n```" for path, content in files.items())
        criterion_lines = "\n".join(
            f"- id: {c.get('id')} | max_points: {c.get('max_points')} | {c.get('description')}" for c in criteria
        )
        messages = [
            SystemMessage(
                content=(
                    "You are a specialist grader for one rubric area. "
                    "Assess only the listed criteria. Reply with JSON only: "
                    '{"findings":[{"id":"...","level":"missing|partial|met","evidence":"..."}]}'
                )
            ),
            HumanMessage(
                content=(
                    f"Area: {area}\nProject: {payload.get('project_id')}\n"
                    f"Assess the following criteria:\n{criterion_lines}\n\n"
                    f"Submission files:\n{file_blob or '(none)'}\n\n"
                    f"JUnit summary: {json.dumps(payload.get('junit') or {})}"
                )
            ),
        ]
        response = model.invoke(messages)
        data = _extract_json(str(response.content))
        by_id = {str(c.get("id")): c for c in criteria}
        findings: list[CriterionFinding] = []
        for row in data.get("findings") or []:
            cid = str(row.get("id") or "")
            criterion = by_id.get(cid)
            if not criterion:
                continue
            level = _normalize_level(row.get("level"))
            max_points = int(criterion.get("max_points") or 0)
            findings.append(
                CriterionFinding(
                    id=cid,
                    area=area,
                    level=level,
                    evidence=str(row.get("evidence") or "")[:500],
                    points=points_for_level(max_points, level),
                    max=max_points,
                )
            )
        # Ensure every criterion in the area has a finding.
        seen = {f["id"] for f in findings}
        for criterion in criteria:
            cid = str(criterion.get("id"))
            if cid in seen:
                continue
            max_points = int(criterion.get("max_points") or 0)
            findings.append(
                CriterionFinding(
                    id=cid,
                    area=area,
                    level="missing",
                    evidence="Specialist did not return a finding.",
                    points=0,
                    max=max_points,
                )
            )
        return {"findings": findings}

    return specialist


def make_verifier_node(model: BaseChatModel):
    def verifier(state: EvaluationState) -> dict[str, Any]:
        findings = list(state.get("findings") or [])
        rubric = state.get("rubric") or {}
        criteria_by_id = {str(c.get("id")): c for c in rubric.get("criteria") or []}
        payload = {
            "findings": [
                {
                    "id": f.get("id"),
                    "area": f.get("area"),
                    "level": f.get("level"),
                    "evidence": f.get("evidence"),
                    "max": f.get("max"),
                }
                for f in findings
            ]
        }
        messages = [
            SystemMessage(
                content=(
                    "You verify rubric findings. You may only downgrade a level when evidence "
                    "does not support it. You cannot invent criteria or raise points. "
                    'Reply with JSON only: {"findings":[{"id":"...","level":"missing|partial|met","evidence":"..."}]}'
                )
            ),
            HumanMessage(
                content=(
                    "Verify these findings against the submission evidence.\n"
                    f"{json.dumps(payload)}\n\n"
                    f"Submission files keys: {list((state.get('submission_files') or {}).keys())}"
                )
            ),
        ]
        response = model.invoke(messages)
        data = _extract_json(str(response.content))
        original = {str(f.get("id")): f for f in findings}
        verified: list[CriterionFinding] = []
        for row in data.get("findings") or []:
            cid = str(row.get("id") or "")
            base = original.get(cid)
            if not base:
                continue
            old_level = _normalize_level(base.get("level"))
            new_level = _normalize_level(row.get("level"))
            # Only allow downgrades.
            order = {"missing": 0, "partial": 1, "met": 2}
            if order[new_level] > order[old_level]:
                new_level = old_level
            max_points = int(base.get("max") or criteria_by_id.get(cid, {}).get("max_points") or 0)
            verified.append(
                CriterionFinding(
                    id=cid,
                    area=str(base.get("area") or ""),
                    level=new_level,
                    evidence=str(row.get("evidence") or base.get("evidence") or "")[:500],
                    points=points_for_level(max_points, new_level),
                    max=max_points,
                )
            )
        # Keep any findings the verifier omitted.
        seen = {v["id"] for v in verified}
        for finding in findings:
            if finding.get("id") in seen:
                continue
            verified.append(finding)
        return {"verified": verified}

    return verifier


def score_node(state: EvaluationState) -> dict[str, Any]:
    verified = list(state.get("verified") or state.get("findings") or [])
    score = compute_score(verified, state.get("rubric") or {})
    return {"score": score, "verified": verified}


def make_feedback_node(model: BaseChatModel):
    def feedback_writer(state: EvaluationState) -> dict[str, Any]:
        score = state.get("score") or {}
        messages = [
            SystemMessage(
                content=(
                    "You are a feedback writer for a certification project. "
                    "Write concise learner-facing feedback in markdown. "
                    "Do not change scores or invent criteria. Do not declare a final pass/fail "
                    "certification; the panel decides."
                )
            ),
            HumanMessage(
                content=(
                    f"Project: {state.get('project_id')}\n"
                    f"Recommendation (for panel): {score.get('recommendation')}\n"
                    f"Total: {score.get('total')}/{score.get('max')}\n"
                    f"Criteria: {json.dumps(score.get('criteria') or [])}\n"
                    f"JUnit: {json.dumps(state.get('junit') or {})}"
                )
            ),
        ]
        response = model.invoke(messages)
        return {"feedback_markdown": str(response.content).strip()}

    return feedback_writer


def panel_node(state: EvaluationState) -> dict[str, Any]:
    """Pause for human panel review. Resume is not wired in the POC."""
    interrupt(
        {
            "evaluation_id": state.get("evaluation_id"),
            "recommendation": (state.get("score") or {}).get("recommendation"),
            "total": (state.get("score") or {}).get("total"),
            "status": "awaiting_panel",
        }
    )
    return {"status": "awaiting_panel"}


def build_graph(*, dry_run: bool = False, checkpointer: MemorySaver | None = None):
    model = get_chat_model(dry_run=dry_run)
    graph = StateGraph(EvaluationState)
    graph.add_node("route", route_node)
    graph.add_node("specialist", make_specialist_node(model))
    graph.add_node("verifier", make_verifier_node(model))
    graph.add_node("score", score_node)
    graph.add_node("feedback", make_feedback_node(model))
    graph.add_node("panel", panel_node)

    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", route_to_specialists, ["specialist", "verifier"])
    graph.add_edge("specialist", "verifier")
    graph.add_edge("verifier", "score")
    graph.add_edge("score", "feedback")
    graph.add_edge("feedback", "panel")
    graph.add_edge("panel", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=saver)


def run_evaluation(initial: EvaluationState, *, dry_run: bool = False, thread_id: str | None = None) -> tuple[EvaluationState, Any]:
    """Run until the panel interrupt. Returns final values and the graph object."""
    checkpointer = MemorySaver()
    app = build_graph(dry_run=dry_run, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id or initial.get("evaluation_id") or "eval"}}
    try:
        app.invoke(initial, config=config)
    except Exception:
        # interrupt() raises GraphInterrupt in some versions; state is still saved.
        pass
    snapshot = app.get_state(config)
    values = dict(snapshot.values) if snapshot and snapshot.values else dict(initial)
    if values.get("status") != "error":
        values["status"] = "awaiting_panel"
    return values, app  # type: ignore[return-value]
