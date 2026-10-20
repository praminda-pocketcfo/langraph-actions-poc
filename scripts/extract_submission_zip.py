"""Extract an uploaded project zip for the evaluation workflow.

Strips one wrapping folder when the archive is a zipped directory. Refuses
paths that escape the destination.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

MAX_UNCOMPRESSED = 32 * 1024 * 1024
MAX_FILES = 4000


def extract_submission_zip(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [_normalize(info.filename) for info in infos]
        names = [name for name in names if name and not _skip(name)]
        for name in names:
            _assert_safe_rel(name)
        if len(names) > MAX_FILES:
            raise ValueError(f"Zip has {len(names)} files. Limit is {MAX_FILES}.")
        root = _common_root(names)
        total = 0
        for info in infos:
            name = _normalize(info.filename)
            if not name or _skip(name):
                continue
            rel = name[len(root) + 1 :] if root and name.startswith(root + "/") else name
            if not rel or _skip(rel):
                continue
            total += info.file_size
            if total > MAX_UNCOMPRESSED:
                raise ValueError("Zip expands past 32 MB.")
            target = _safe_target(dest, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as out:
                out.write(src.read())


def _normalize(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _skip(name: str) -> bool:
    parts = [part for part in name.split("/") if part]
    return not parts or any(part == "__MACOSX" or part == ".DS_Store" for part in parts)


def _common_root(names: list[str]) -> str | None:
    if not names or not all("/" in name for name in names):
        return None
    roots = {name.split("/", 1)[0] for name in names}
    if len(roots) != 1:
        return None
    return next(iter(roots))


def _assert_safe_rel(rel: str) -> None:
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or any(part == "" for part in path.parts):
        raise ValueError(f"Unsafe path in zip: {rel}")


def _safe_target(dest: Path, rel: str) -> Path:
    _assert_safe_rel(rel)
    root = dest.resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Unsafe path in zip: {rel}")
    return target


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: extract_submission_zip.py ZIP DEST", file=sys.stderr)
        return 2
    zip_path, dest = Path(argv[1]), Path(argv[2])
    try:
        extract_submission_zip(zip_path, dest)
    except (zipfile.BadZipFile, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
