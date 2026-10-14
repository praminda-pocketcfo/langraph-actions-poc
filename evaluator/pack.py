"""Load evaluation packs from disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .state import Rubric


def packs_root(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "packs"


def load_manifest(project_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    path = packs_root(repo_root) / project_id / "manifest.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown project pack: {project_id} ({path})")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if data.get("project_id") != project_id:
        raise ValueError(f"manifest project_id mismatch for {project_id}")
    return data


def load_rubric(project_id: str, repo_root: Path | None = None) -> Rubric:
    path = packs_root(repo_root) / project_id / "rubric.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing rubric for {project_id}: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return Rubric(**data)


def pack_tests_dir(project_id: str, repo_root: Path | None = None) -> Path:
    return packs_root(repo_root) / project_id / "tests"


def list_pack_ids(repo_root: Path | None = None) -> list[str]:
    root = packs_root(repo_root)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "manifest.yaml").exists())
