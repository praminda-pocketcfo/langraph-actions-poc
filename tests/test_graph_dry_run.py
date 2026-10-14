from pathlib import Path

from evaluator.graph import run_evaluation
from evaluator.pack import load_rubric
from evaluator.state import EvaluationState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "word_counter_partial" / "word_counter.py"


def test_dry_run_graph_reaches_awaiting_panel():
    rubric = load_rubric("word_counter", ROOT)
    initial: EvaluationState = {
        "evaluation_id": "00000000-0000-4000-8000-000000000001",
        "submission_repo": "example/submission",
        "pr_number": 1,
        "head_sha": "abc123",
        "project_id": "word_counter",
        "run_url": "",
        "submission_files": {"word_counter.py": FIXTURE.read_text(encoding="utf-8")},
        "junit": {"passed": 5, "failed": 1, "errors": 0, "total": 6, "details": []},
        "rubric": rubric,
        "findings": [],
        "status": "running",
    }
    final_state, _app = run_evaluation(initial, dry_run=True, thread_id="dry-run-test")
    assert final_state["status"] == "awaiting_panel"
    score = final_state.get("score") or {}
    assert score.get("total") is not None
    assert score.get("recommendation") in {"pass", "borderline", "fail"}
    assert final_state.get("feedback_markdown")
    criteria_ids = {c["id"] for c in score.get("criteria") or []}
    assert "unit_tests" in criteria_ids
    assert "handles_edge_cases" in criteria_ids
    assert "clear_structure" in criteria_ids
