import pytest

from scripts.download_drive_file import file_id_from_url


def test_file_id_from_standard_drive_link():
    assert (
        file_id_from_url("https://drive.google.com/file/d/abc123_XYZ/view")
        == "abc123_XYZ"
    )


def test_file_id_from_query_link():
    assert (
        file_id_from_url("https://drive.usercontent.google.com/download?id=file-1&export=download")
        == "file-1"
    )


def test_rejects_non_drive_host():
    with pytest.raises(ValueError, match="Google Drive"):
        file_id_from_url("https://example.com/file/d/abc/view")
