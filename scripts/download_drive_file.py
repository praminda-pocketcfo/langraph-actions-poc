"""Download a submission zip from Google Drive with the official client."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
ALLOWED_HOSTS = {"drive.google.com", "docs.google.com", "drive.usercontent.google.com"}


def file_id_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ValueError("submission_url must be an https Google Drive link")
    marker = "/file/d/"
    if marker in parsed.path:
        file_id = parsed.path.split(marker, 1)[1].split("/", 1)[0]
        if file_id:
            return file_id
    file_id = parse_qs(parsed.query).get("id", [""])[0]
    if file_id:
        return file_id
    raise ValueError("Could not find a Drive file id in submission_url")


def download_drive_file(url: str, dest: Path) -> None:
    file_id = file_id_from_url(url)
    credentials = service_account.Credentials.from_service_account_info(
        load_service_account(),
        scopes=[DRIVE_READONLY],
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def load_service_account() -> dict:
    encoded = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    text = base64.b64decode(encoded).decode("utf-8") if encoded else raw
    if not text:
        raise RuntimeError(
            "Set GOOGLE_SERVICE_ACCOUNT_JSON on the evaluation repo, or GOOGLE_SERVICE_ACCOUNT_JSON_BASE64."
        )
    info = json.loads(text)
    if "client_email" not in info or "private_key" not in info:
        raise RuntimeError("Service account JSON needs client_email and private_key.")
    return info


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: download_drive_file.py SUBMISSION_URL DEST", file=sys.stderr)
        return 2
    try:
        download_drive_file(argv[1], Path(argv[2]))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
