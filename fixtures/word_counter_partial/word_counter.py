"""Partial word_counter solution used for dry-run evaluation fixtures."""


def count_words(text: str) -> int:
    """Count whitespace-separated words. Empty and whitespace-only inputs return 0."""
    if not text or not text.strip():
        return 0
    return len(text.split())
