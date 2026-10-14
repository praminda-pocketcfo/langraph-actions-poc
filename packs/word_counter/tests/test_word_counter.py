"""Instructor tests for the word_counter project."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SUBMISSION = Path(__file__).resolve().parents[1] / "submission" / "word_counter.py"


def _load_module():
    if not SUBMISSION.exists():
        pytest.fail(f"Missing submission file: {SUBMISSION}")
    spec = importlib.util.spec_from_file_location("word_counter", SUBMISSION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def count_words():
    module = _load_module()
    if not hasattr(module, "count_words"):
        pytest.fail("Submission must define count_words(text: str) -> int")
    return module.count_words


def test_simple_sentence(count_words):
    assert count_words("hello world") == 2


def test_single_word(count_words):
    assert count_words("hello") == 1


def test_empty_string(count_words):
    assert count_words("") == 0


def test_only_whitespace(count_words):
    assert count_words("   \t\n  ") == 0


def test_leading_and_trailing_whitespace(count_words):
    assert count_words("  hello world  ") == 2


def test_multiple_spaces_between_words(count_words):
    assert count_words("one   two    three") == 3
