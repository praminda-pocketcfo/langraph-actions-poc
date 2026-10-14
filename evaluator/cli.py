"""CLI entrypoint for GitHub Actions and local dry-runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import github_io, neon
from .graph import run_evaluation
from .junit import parse_junit
from .pack import load_manifest, load_rubric
from .publish import publish
from .result import build_result
from .state import EvaluationState


def _repo_root() -> Path:
    return Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd()).resolve()


def _load_submission_from_dir(directory: Path, paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in paths:
        path = directory / rel
        if not path.exists():
            raise FileNotFoundError(f"Missing submission file: {path}")
        files[rel] = path.read_text(encoding="utf-8")[:12000]
    return files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run learner project evaluation")
    parser.add_argument("--evaluation-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--submission-repo", default="")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--junit", type=Path, default=None)
    parser.add_argument("--submission-dir", type=Path, default=None, help="Local dir with submission files (fixture/dry-run)")
    parser.add_argument("--run-url", default=os.environ.get("GITHUB_RUN_URL", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument(
        "--write-neon",
        action="store_true",
        help="Persist result to Neon (requires DATABASE_URL). Off by default for the POC.",
    )
    parser.add_argument("--mark-error", default="", help="Record an error (Neon only if --write-neon) and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = bool(args.dry_run)
    write_neon = bool(args.write_neon)
    skip_neon = not write_neon
    root = _repo_root()

    if args.mark_error:
        payload = {
            "version": 1,
            "evaluation_id": args.evaluation_id,
            "status": "error",
            "error": args.mark_error,
            "run_url": args.run_url or "",
        }
        print(json.dumps(payload, indent=2))
        if write_neon and not dry_run:
            neon.mark_error(args.evaluation_id, args.mark_error, run_url=args.run_url or None)
        return 1

    try:
        manifest = load_manifest(args.project_id, root)
        rubric = load_rubric(args.project_id, root)
        paths = list(manifest.get("submission_paths") or [])

        head_sha = args.head_sha
        if args.submission_dir:
            submission_files = _load_submission_from_dir(Path(args.submission_dir), paths)
        elif args.submission_repo and args.pr_number:
            if write_neon and not dry_run:
                neon.mark_running(args.evaluation_id, head_sha=head_sha or None, run_url=args.run_url or None)
            pr = github_io.get_pull_request(args.submission_repo, args.pr_number)
            head_sha = head_sha or (pr.get("head") or {}).get("sha") or ""
            submission_files = github_io.fetch_submission_files(
                args.submission_repo,
                head_sha=head_sha,
                paths=paths,
            )
        else:
            raise SystemExit("Provide --submission-dir or --submission-repo with --pr-number")

        junit = parse_junit(args.junit) if args.junit else {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total": 0,
            "details": [],
        }

        initial: EvaluationState = {
            "evaluation_id": args.evaluation_id,
            "submission_repo": args.submission_repo,
            "pr_number": int(args.pr_number or 0),
            "head_sha": head_sha,
            "project_id": args.project_id,
            "run_url": args.run_url,
            "submission_files": submission_files,
            "junit": junit,  # type: ignore[typeddict-item]
            "rubric": rubric,
            "findings": [],
            "status": "running",
        }

        final_state, _app = run_evaluation(initial, dry_run=dry_run, thread_id=args.evaluation_id)
        result = publish(
            final_state,
            dry_run=dry_run,
            skip_github=args.skip_github or dry_run,
            skip_neon=skip_neon or dry_run,
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        print(
            json.dumps(
                build_result(  # type: ignore[arg-type]
                    {
                        "evaluation_id": args.evaluation_id,
                        "status": "error",
                        "error": message,
                        "run_url": args.run_url,
                    }
                ),
                indent=2,
            )
        )
        if write_neon and not dry_run:
            try:
                neon.mark_error(args.evaluation_id, message, run_url=args.run_url or None)
            except Exception as nested:
                print(f"failed to mark error in Neon: {nested}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
