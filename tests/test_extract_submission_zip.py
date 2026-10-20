import zipfile
from pathlib import Path

import pytest

from scripts.extract_submission_zip import extract_submission_zip


def test_strips_wrapper_folder(tmp_path: Path):
    archive_path = tmp_path / "upload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("my-repo/word_counter.py", "def count_words(text):\n    return 1\n")
        archive.writestr("my-repo/.git/HEAD", "ref: refs/heads/main\n")

    dest = tmp_path / "out"
    extract_submission_zip(archive_path, dest)

    assert (dest / "word_counter.py").read_text(encoding="utf-8").startswith("def count_words")
    assert (dest / ".git" / "HEAD").is_file()
    assert not (dest / "my-repo").exists()


def test_rejects_path_traversal(tmp_path: Path):
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../secret.txt", "nope")
    with pytest.raises(ValueError, match="Unsafe path"):
        extract_submission_zip(archive_path, tmp_path / "out")
