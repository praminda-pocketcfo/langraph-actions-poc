from pathlib import Path

from evaluator.pack import list_pack_ids, load_manifest, load_rubric

ROOT = Path(__file__).resolve().parents[1]


def test_word_counter_pack_loads():
    assert "word_counter" in list_pack_ids(ROOT)
    manifest = load_manifest("word_counter", ROOT)
    assert manifest["submission_paths"] == ["word_counter.py"]
    rubric = load_rubric("word_counter", ROOT)
    assert len(rubric["criteria"]) == 3
