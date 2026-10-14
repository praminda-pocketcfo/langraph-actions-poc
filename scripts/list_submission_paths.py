#!/usr/bin/env python3
"""Print submission_paths from a pack manifest (one path per line)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: list_submission_paths.py <project_id>", file=sys.stderr)
        return 2
    project_id = sys.argv[1]
    path = Path("packs") / project_id / "manifest.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for rel in data.get("submission_paths") or []:
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
