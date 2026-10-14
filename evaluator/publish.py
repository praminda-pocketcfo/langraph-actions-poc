"""Publish evaluation outputs to Neon and GitHub."""

from __future__ import annotations

import os
from typing import Any

from . import github_io, neon
from .result import build_result, serializable_state
from .state import EvaluationState


def publish(state: EvaluationState, *, dry_run: bool = False, skip_github: bool = False) -> dict[str, Any]:
    result = build_result(state)
    evaluation_id = state.get("evaluation_id")
    if not evaluation_id:
        raise RuntimeError("evaluation_id is required to publish")

    if dry_run or os.environ.get("EVAL_DRY_RUN", "").lower() in {"1", "true", "yes"}:
        return result

    neon.publish_result(
        evaluation_id,
        result=result,
        state=serializable_state(state),
        recommendation=result.get("recommendation"),
        head_sha=state.get("head_sha"),
        run_url=state.get("run_url"),
    )

    if not skip_github and state.get("submission_repo") and state.get("pr_number"):
        github_io.upsert_evaluation_comment(
            str(state["submission_repo"]),
            int(state["pr_number"]),
            result,
        )
    return result
