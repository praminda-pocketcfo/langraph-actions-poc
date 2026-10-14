"""Publish evaluation outputs to GitHub (and optionally Neon)."""

from __future__ import annotations

from typing import Any

from . import github_io, neon
from .result import build_result, serializable_state
from .state import EvaluationState


def publish(
    state: EvaluationState,
    *,
    skip_github: bool = False,
    skip_neon: bool = True,
) -> dict[str, Any]:
    """Publish result JSON consumers.

    `--dry-run` only selects the fake model; it does not skip the PR comment.
    Pass ``skip_github=True`` to print JSON only. Neon stays off unless
    ``skip_neon=False`` (CLI ``--write-neon``).
    """
    result = build_result(state)
    evaluation_id = state.get("evaluation_id")
    if not evaluation_id:
        raise RuntimeError("evaluation_id is required to publish")

    if not skip_neon:
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
