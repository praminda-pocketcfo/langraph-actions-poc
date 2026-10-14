"""Build the versioned evaluation result payload."""

from __future__ import annotations

from typing import Any

from .state import EvaluationState

RESULT_MARKER = "<!-- learner-evaluation:v1 -->"
RESULT_VERSION = 1


def build_result(state: EvaluationState) -> dict[str, Any]:
    score = state.get("score") or {}
    junit = state.get("junit") or {}
    return {
        "version": RESULT_VERSION,
        "evaluation_id": state.get("evaluation_id"),
        "pr": state.get("pr_number"),
        "project_id": state.get("project_id"),
        "head_sha": state.get("head_sha"),
        "run_url": state.get("run_url"),
        "test": {
            "passed": int(junit.get("passed") or 0),
            "failed": int(junit.get("failed") or 0),
            "errors": int(junit.get("errors") or 0),
        },
        "criteria": score.get("criteria") or state.get("verified") or [],
        "total": score.get("total"),
        "max": score.get("max"),
        "recommendation": score.get("recommendation"),
        "status": state.get("status") or "awaiting_panel",
        "feedback_markdown": state.get("feedback_markdown") or "",
    }


def format_comment(result: dict[str, Any]) -> str:
    import json

    rec = result.get("recommendation") or "unknown"
    total = result.get("total")
    maximum = result.get("max")
    status = result.get("status")
    feedback = result.get("feedback_markdown") or ""
    body = (
        f"{RESULT_MARKER}\n"
        f"## Learner evaluation\n\n"
        f"- Project: `{result.get('project_id')}`\n"
        f"- Recommendation: **{rec}** ({total}/{maximum})\n"
        f"- Status: `{status}`\n"
        f"- Evaluation id: `{result.get('evaluation_id')}`\n\n"
        f"{feedback}\n\n"
        f"```json\n{json.dumps(result, indent=2)}\n```\n"
    )
    return body


def serializable_state(state: EvaluationState) -> dict[str, Any]:
    """Drop non-JSON fields before storing graph state for a later resume."""
    skip = {"messages"}
    return {k: v for k, v in dict(state).items() if k not in skip}
